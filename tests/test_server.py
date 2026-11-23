"""The server Lambda, called in-process: the page, sign-in, config, the example items API."""
import importlib
import json
import os

import pytest

from fakes import FakeS3, basic

lf = importlib.import_module(os.environ["PACKAGE"] + ".server.lambda_function")


@pytest.fixture(autouse=True)
def aws(monkeypatch):
    s3 = FakeS3()
    monkeypatch.setattr(lf, "s3", s3)
    return s3


def call(method, path, body=None, auth=True):
    event = {"requestContext": {"http": {"method": method}}, "rawPath": path,
             "headers": {"authorization": basic()} if auth else {}}
    if body is not None:
        event["body"] = json.dumps(body)
    r = lf.lambda_handler(event, None)
    if r["headers"]["content-type"] != "application/json":
        return r["statusCode"], r
    data = json.loads(r["body"])
    data.pop("ms", None)
    return r["statusCode"], data


def items():
    return call("GET", "/api/items")[1]["items"]


def test_page_is_public_and_carries_the_version():
    status, r = call("GET", "/", auth=False)
    assert status == 200 and lf.VERSION in r["body"] and "script-src 'sha256-" in r["headers"]["content-security-policy"]


def test_api_needs_sign_in():
    assert call("GET", "/api/items", auth=False)[0] == 401


def test_bad_credentials_are_rejected():
    event = {"requestContext": {"http": {"method": "GET"}}, "rawPath": "/api/ping",
             "headers": {"authorization": basic(password="wrong")}}
    assert lf.lambda_handler(event, None)["statusCode"] == 401


def test_config():
    status, r = call("GET", "/api/config")
    assert status == 200 and r["version"] == lf.VERSION


def test_no_items_at_first():
    assert items() == []


def test_create_list_delete(aws):
    status, r = call("POST", "/api/items", {"name": "alpha"})
    assert status == 201 and r["item"]["name"] == "alpha" and r["item"]["by"] == "admin"
    assert "items/alpha.json" in aws.objects
    assert [i["name"] for i in items()] == ["alpha"]
    status, r = call("POST", "/api/items/alpha/delete")
    assert status == 200 and r["deleted"] == "alpha" and items() == []


def test_duplicate_is_a_conflict():
    call("POST", "/api/items", {"name": "alpha"})
    assert call("POST", "/api/items", {"name": "alpha"})[0] == 409


@pytest.mark.parametrize("name", ["bad name!", "", "x" * 65, None])
def test_bad_name_is_rejected(name):
    assert call("POST", "/api/items", {"name": name})[0] == 400


def test_delete_missing_is_not_found():
    assert call("POST", "/api/items/ghost/delete")[0] == 404
