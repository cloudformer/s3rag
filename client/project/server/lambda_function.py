"""<project> server: one Lambda behind a Function URL — JSON API for the client, web console at GET /.

Template. The first half (JSON, request body, sign-in, routing, error mapping, timing) is the series'
shared shell — identical in every project; replace the example "items" routes in the second half.

Sign-in: two methods, each on or off; a request passes when any method that is on accepts it.
    HTTP_AUTH=1        HTTP Basic (USER_NAME / PASSWORD). Identity = the user name.
    CLOUDFLARE_AUTH=1  Cloudflare Access: the Cf-Access-Jwt-Assertion header, an RS256 JWT checked against
                       the team's public keys, aud, issuer and expiry. Identity = the email in it.

    GET  / , /api/ping , /api/me
    GET  /api/config                 what the page needs (names, limits, version)
    GET  /api/items                  example list (items/<name>.json in the bucket)
    POST /api/items                  {"name"}: example create
    POST /api/items/<name>/delete    example delete

Layout: items/<name>.json ({"name", "created", "by"}). Replace with the project's own primitives.
"""
import base64
import datetime
import hashlib
import json
import os
import re
import time
import urllib.parse

import boto3

import idlefree_auth as auth
import idlefree_ui

BUCKET = os.environ.get("BUCKET", "")
PROJECT = os.environ.get("PROJECT", "")
REGION = os.environ.get("AWS_REGION", "")
ITEMS = "items/"
LIST_LIMIT = 100

HERE = os.path.dirname(__file__)
with open(os.path.join(HERE, "..", "__init__.py"), encoding="utf-8") as f:
    VERSION = re.search(r'__version__ = "([^"]+)"', f.read()).group(1)
with open(os.path.join(HERE, "index.html"), encoding="utf-8") as f:
    INDEX_HTML = f.read().replace("__VERSION__", VERSION).replace("/* idlefree-ui */", idlefree_ui.CSS)

# Every inline <script> is hashed into the CSP: the page runs only the scripts shipped here, nothing injected.
_HASHES = " ".join("'sha256-%s'" % base64.b64encode(hashlib.sha256(s.encode()).digest()).decode()
                   for s in re.findall(r"<script>(.*?)</script>", INDEX_HTML, re.S))
CSP = (f"default-src 'none'; script-src {_HASHES}; style-src 'unsafe-inline'; connect-src 'self'; "
       "img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'")
PAGE_HEADERS = {"content-security-policy": CSP, "x-content-type-options": "nosniff",
                "referrer-policy": "no-referrer", "x-frame-options": "DENY"}

NAME = re.compile(r"[A-Za-z0-9_-]{1,64}")

s3 = boto3.client("s3")


class BadRequest(Exception):
    pass


class Forbidden(Exception):
    pass


class NotFound(Exception):
    pass


class Conflict(Exception):
    pass


# ---------------- shared: the same shell as the rest of the series ----------------

def _json(status, data):
    return {"statusCode": status, "headers": {"content-type": "application/json"},
            "body": json.dumps(data, ensure_ascii=False, default=str)}


def _body(event):
    raw = event.get("body") or "{}"
    try:
        if event.get("isBase64Encoded"):
            raw = base64.b64decode(raw)
        data = json.loads(raw)
    except ValueError:
        raise BadRequest("request body is not valid JSON") from None
    if not isinstance(data, dict):
        raise BadRequest("request body must be a JSON object")
    return data


ERRORS = [(BadRequest, 400), (Forbidden, 403), (NotFound, 404), (Conflict, 409)]


def lambda_handler(event, context):
    http = (event.get("requestContext") or {}).get("http") or {}
    method, path = http.get("method", "GET"), urllib.parse.unquote(event.get("rawPath", "/"))
    problem = auth.problem()
    if problem:
        return _json(503, {"error": problem})
    signed = auth.identity(event)
    if signed is None and not auth.HTTP_AUTH:
        return _json(401, {"error": "sign in through Cloudflare Access", "http_auth": False})
    if method == "GET" and path in ("/", "/index.html"):
        return {"statusCode": 200, "body": INDEX_HTML,
                "headers": dict(PAGE_HEADERS, **{"content-type": "text/html; charset=utf-8", "cache-control": "no-cache"})}
    if signed is None:
        return _json(401, {"error": "bad credentials", "http_auth": True})
    event["identity"], event["auth_method"] = signed
    t0 = time.perf_counter()
    status, data = 404, {"error": f"no route: {method} {path}"}
    try:
        for route_method, pattern, handler in ROUTES:
            match = pattern.fullmatch(path)
            if match and route_method == method:
                out = handler(event, **match.groupdict())
                status, data = out if isinstance(out, tuple) else (200, out)
                break
    except Exception as e:  # noqa: BLE001
        status = next((s for cls, s in ERRORS if isinstance(e, cls)), 500)
        data = {"error": str(e) if status < 500 else f"{type(e).__name__}: {e}"}
    data.setdefault("ms", round((time.perf_counter() - t0) * 1000, 1))
    return _json(status, data)


# ---------------- the project's API: replace these example routes ----------------

def _iso(t):
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _name(value):
    if not isinstance(value, str) or not NAME.fullmatch(value):
        raise BadRequest(f"name: letters, digits, _ or -, at most 64, got {value!r}")
    return value


def _get(key):
    try:
        return json.loads(s3.get_object(Bucket=BUCKET, Key=key)["Body"].read())
    except s3.exceptions.NoSuchKey:
        return None


def ping(event):
    return {"ok": True}


def me(event):
    return {"identity": event["identity"], "auth_method": event["auth_method"]}


def config(event):
    return {"project": PROJECT, "region": REGION, "list_limit": LIST_LIMIT, "version": VERSION}


def list_items(event):
    names = []
    for page in s3.get_paginator("list_objects_v2").paginate(Bucket=BUCKET, Prefix=ITEMS):
        names += [o["Key"][len(ITEMS):-len(".json")] for o in page.get("Contents", [])]
    items = [_get(f"{ITEMS}{n}.json") for n in sorted(names)[:LIST_LIMIT]]
    return {"items": [i for i in items if i]}


def create_item(event):
    name = _name(_body(event).get("name", ""))
    key = f"{ITEMS}{name}.json"
    if _get(key) is not None:
        raise Conflict(f"item {name} exists")
    item = {"name": name, "created": _iso(datetime.datetime.now(datetime.timezone.utc)), "by": event["identity"]}
    s3.put_object(Bucket=BUCKET, Key=key, ContentType="application/json", Body=json.dumps(item).encode())
    print(json.dumps({"event": "item_created", "name": name, "by": event["identity"]}))
    return 201, {"item": item}


def delete_item(event, name):
    _name(name)
    key = f"{ITEMS}{name}.json"
    if _get(key) is None:
        raise NotFound(f"no item {name}")
    s3.delete_object(Bucket=BUCKET, Key=key)
    print(json.dumps({"event": "item_deleted", "name": name, "by": event["identity"]}))
    return {"deleted": name}


ROUTES = [
    ("GET",  re.compile(r"/api/ping"), ping),
    ("GET",  re.compile(r"/api/me"), me),
    ("GET",  re.compile(r"/api/config"), config),
    ("GET",  re.compile(r"/api/items"), list_items),
    ("POST", re.compile(r"/api/items"), create_item),
    ("POST", re.compile(r"/api/items/(?P<name>[^/]+)/delete"), delete_item),
]
