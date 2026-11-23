"""Fakes for the AWS clients the Lambda uses, and the Basic-auth helper: no AWS account needed.

Its own module (not conftest.py): the repo has two conftest files (tests/ and tests/compat/), and
`from conftest import …` resolves to whichever was imported first — in CI that was the compat one.
"""
import base64
import datetime
import io

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
