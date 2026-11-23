"""Test setup: the package and the idlefree siblings on the import path, env, fakes; the compat-report hooks.

The report hooks must live in the ROOT conftest so they see the whole run (regression + compat).
No AWS account needed: the fixtures below monkeypatch the boto3 clients with fakes.
"""
import base64
import datetime
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIBLINGS = os.path.dirname(ROOT)   # repo-private: idlefree-auth / idlefree-ui live next to the project

# the pip / import name, read from client/pyproject.toml so nothing else hard-codes it
with open(os.path.join(ROOT, "client", "pyproject.toml"), encoding="utf-8") as _f:
    PACKAGE = re.search(r'^name\s*=\s*"([^"]+)"', _f.read(), re.M).group(1)
os.environ["PACKAGE"] = PACKAGE

sys.path[:0] = [os.path.join(ROOT, "client"),
                os.path.join(ROOT, "client", PACKAGE, "server"),   # compat plugins import lambda_function directly
                os.path.join(SIBLINGS, "idlefree-auth"), os.path.join(SIBLINGS, "idlefree-ui")]

# lambda_function reads these at import time
os.environ.update(
    AWS_REGION="us-east-2", AWS_DEFAULT_REGION="us-east-2",
    HTTP_AUTH="1", USER_NAME="admin", PASSWORD="a-password-of-16+chars",
    BUCKET=f"test-{PACKAGE}", PROJECT=f"test-{PACKAGE}")

NOW = datetime.datetime.now(datetime.timezone.utc).replace(microsecond=0)


class FakeS3:
    class exceptions:
        NoSuchKey = type("NoSuchKey", (Exception,), {})

    def __init__(self):
        self.objects = {}

    def put_object(self, Bucket, Key, Body, ContentType=None, IfNoneMatch=None):
        self.objects[Key] = Body

    def get_object(self, Bucket, Key):
        if Key not in self.objects:
            raise self.exceptions.NoSuchKey(Key)
        return {"Body": io.BytesIO(self.objects[Key])}

    def delete_object(self, Bucket, Key):
        self.objects.pop(Key, None)
        return {}

    def get_paginator(self, name):
        objs = self.objects

        class Paginator:
            def paginate(self, Bucket, Prefix=""):
                contents = [{"Key": k, "LastModified": NOW} for k in sorted(objs) if k.startswith(Prefix)]
                yield {"Contents": contents} if contents else {}
        return Paginator()


def basic(user="admin", password="a-password-of-16+chars"):
    return "Basic " + base64.b64encode(f"{user}:{password}".encode()).decode()


from compat_report import (pytest_collection_modifyitems, pytest_configure,  # noqa: E402,F401
                           pytest_runtest_logreport, pytest_sessionfinish, pytest_terminal_summary)


pytest_plugins = ["compat_docker", "compat_aws"]   # python3 -m pytest tests -q [--docker up | run | down] [--aws <var-file>]
