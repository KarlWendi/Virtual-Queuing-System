"""Verify the free-host WSGI entry point against the WSGI specification."""

import importlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit
from wsgiref.util import setup_testing_defaults
from wsgiref.validate import validator
import accounts


class WsgiTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.previous_db = accounts.DB_PATH
        accounts.DB_PATH = Path(self.temp.name) / "queue.sqlite3"
        self.environment = patch.dict(os.environ, {"QUEUE_EMAIL_MODE": "file"})
        self.environment.start()
        self.app = validator(importlib.import_module("wsgi_app").application)
        accounts.initialize()

    def tearDown(self):
        accounts.DB_PATH = self.previous_db
        self.environment.stop()
        self.temp.cleanup()

    def request(self, path, data=None, cookie=None, csrf=None, method=None):
        environ = {}
        setup_testing_defaults(environ)
        body = b"" if data is None else json.dumps(data).encode()
        environ.update(
            {
                "REQUEST_METHOD": method or ("GET" if data is None else "POST"),
                "PATH_INFO": path,
                "CONTENT_LENGTH": str(len(body)),
                "CONTENT_TYPE": "application/json",
                "wsgi.input": io.BytesIO(body),
                "REMOTE_ADDR": "127.0.0.1",
                "HTTP_HOST": "localhost",
                "QUERY_STRING": "",
            }
        )
        if cookie:
            environ["HTTP_COOKIE"] = cookie
        if csrf:
            environ["HTTP_X_CSRF_TOKEN"] = csrf
        result = {}

        def start(status, headers, exc_info=None):
            result["status"] = int(status.split()[0])
            result["headers"] = dict(headers)

        response = self.app(environ, start)
        try:
            payload = b"".join(response)
        finally:
            response.close()
        result["data"] = (
            json.loads(payload)
            if "application/json" in result["headers"]["Content-Type"]
            else payload
        )
        return result

    def test_pages_accounts_and_protected_queue(self):
        for path in (
            "/",
            "/admin",
            "/verify",
            "/reset",
            "/app.js",
            "/style.css",
            "/health",
        ):
            self.assertEqual(self.request(path)["status"], 200)
        self.assertEqual(self.request("/queue")["status"], 401)
        self.assertEqual(self.request("/queue", method="DELETE")["status"], 405)
        result = self.request(
            "/auth/register",
            {
                "name": "Hosted User",
                "email": "hosted@example.test",
                "password": "Long test password 123",
            },
        )
        self.assertEqual(result["status"], 201)
        mail = json.loads(
            next((accounts.DB_PATH.parent / "dev-mail").glob("*.json")).read_text()
        )
        url = mail["text"].split("Open this link: ")[1].splitlines()[0]
        token = parse_qs(urlsplit(url).fragment)["token"][0]
        self.assertEqual(self.request("/auth/verify", {"token": token})["status"], 200)
        result = self.request(
            "/auth/login",
            {"email": "hosted@example.test", "password": "Long test password 123"},
        )
        self.assertEqual(result["status"], 200)
        cookie = result["headers"]["Set-Cookie"].split(";")[0]
        csrf = result["data"]["csrf"]
        self.assertIn("HttpOnly", result["headers"]["Set-Cookie"])
        joined = self.request("/join", {"issue": "Software Issue"}, cookie, csrf)
        self.assertEqual(joined["status"], 201)
        entry_id = joined["data"]["id"]
        self.assertEqual(
            self.request("/queue", cookie=cookie)["data"]["queue"][0]["name"],
            "Hosted User",
        )
        self.assertEqual(self.request("/serve", {}, cookie, csrf)["status"], 403)
        self.assertEqual(
            self.request("/leave", {"id": entry_id}, cookie, csrf)["status"], 200
        )
        self.assertEqual(self.request("/auth/logout", {}, cookie, csrf)["status"], 200)
        self.assertEqual(self.request("/queue", cookie=cookie)["status"], 401)


if __name__ == "__main__":
    unittest.main()
