"""Integration checks use an isolated temporary database and development mailbox."""

import http.cookiejar
import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.parse import urlsplit, parse_qs
from urllib.request import Request, build_opener, HTTPCookieProcessor
import accounts
import server


class AccountsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.old_db = accounts.DB_PATH
        cls.old_mode = os.environ.get("QUEUE_EMAIL_MODE")
        accounts.DB_PATH = Path(cls.temp.name) / "queue.sqlite3"
        os.environ["QUEUE_EMAIL_MODE"] = "file"
        accounts.initialize()
        cls.server = server.ThreadingHTTPServer(
            ("127.0.0.1", 0), server.QueueRequestHandler
        )
        cls.url = f"http://127.0.0.1:{cls.server.server_port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join()
        accounts.DB_PATH = cls.old_db
        if cls.old_mode is None:
            os.environ.pop("QUEUE_EMAIL_MODE", None)
        else:
            os.environ["QUEUE_EMAIL_MODE"] = cls.old_mode
        cls.temp.cleanup()

    def browser(self):
        return build_opener(HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def request(self, browser, path, data=None, csrf=None, extra=None):
        headers = {"Content-Type": "application/json"}
        if csrf:
            headers["X-CSRF-Token"] = csrf
        if extra:
            headers.update(extra)
        req = Request(
            self.url + path,
            data=None if data is None else json.dumps(data).encode(),
            headers=headers,
        )
        try:
            with browser.open(req, timeout=10) as response:
                return response.status, json.load(response), response.headers
        except HTTPError as error:
            with error:
                return error.code, json.load(error), error.headers

    def link(self, email, kind):
        files = sorted(
            (accounts.DB_PATH.parent / "dev-mail").glob("*.json"),
            key=lambda p: p.stat().st_mtime_ns,
        )
        messages = [json.loads(p.read_text()) for p in files]
        subject = "Verify" if kind == "verify" else "Reset"
        msg = next(
            m
            for m in reversed(messages)
            if m["to"] == email and m["subject"].startswith(subject)
        )
        url = msg["text"].split("Open this link: ")[1].splitlines()[0]
        return parse_qs(urlsplit(url).fragment)["token"][0]

    def register(self, b, email, name):
        data = {"email": email, "name": name, "password": "Long test password 123"}
        self.assertEqual(self.request(b, "/auth/register", data)[0], 201)
        return self.link(email, "verify")

    def login(self, b, email, password="Long test password 123"):
        code, result, headers = self.request(
            b, "/auth/login", {"email": email, "password": password}
        )
        self.assertEqual(code, 200)
        self.assertIn("HttpOnly", headers["Set-Cookie"])
        self.assertIn("SameSite=Lax", headers["Set-Cookie"])
        return result["csrf"]

    def test_invalid_inputs_sessions_and_parallel_joins(self):
        from concurrent.futures import ThreadPoolExecutor

        browser = self.browser()
        for data in (
            {
                "name": "Test",
                "email": "not-an-email",
                "password": "Long test password 123",
            },
            {"name": "Test", "email": "invalid@example.test", "password": "short"},
            {
                "name": "",
                "email": "empty@example.test",
                "password": "Long test password 123",
            },
        ):
            self.assertEqual(self.request(browser, "/auth/register", data)[0], 400)
        with accounts.connect() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT id FROM users WHERE email='invalid@example.test'"
                ).fetchone()
            )

        token = self.register(browser, "expired@example.test", "Expired")
        with accounts.connect() as db:
            db.execute(
                "UPDATE links SET expires=0 WHERE hash=?", (accounts.digest(token),)
            )
        self.assertEqual(
            self.request(browser, "/auth/verify", {"token": token})[0], 400
        )
        self.request(browser, "/auth/resend", {"email": "expired@example.test"})
        token = self.link("expired@example.test", "verify")
        self.assertEqual(
            self.request(browser, "/auth/verify", {"token": token})[0], 200
        )
        csrf = self.login(browser, "expired@example.test")
        with accounts.connect() as db:
            db.execute(
                "UPDATE sessions SET expires=0 WHERE user_id=(SELECT id FROM users WHERE email='expired@example.test')"
            )
        self.assertEqual(
            self.request(browser, "/join", {"issue": "Software Issue"}, csrf)[0], 401
        )
        self.assertIsNone(self.request(browser, "/auth/me")[1]["user"])

        # Concurrent requests from one account still create only one place.
        user = {
            "id": "parallel-user",
            "name": "Parallel",
            "verified": 1,
            "role": "client",
        }
        with accounts.connect() as db:
            db.execute(
                "INSERT INTO users(id,email,name,password,verified) VALUES(?,?,?,?,1)",
                (
                    user["id"],
                    "parallel@example.test",
                    user["name"],
                    accounts.password_hash("Long test password 123"),
                ),
            )

        def join_once(_):
            try:
                return accounts.queue_action(user, "/join", {"issue": "Software Issue"})
            except accounts.AppError as error:
                return error.status

        with ThreadPoolExecutor(max_workers=5) as pool:
            results = list(pool.map(join_once, range(5)))
        self.assertEqual(sum(isinstance(result, dict) for result in results), 1)
        self.assertEqual(results.count(409), 4)
        current = accounts.own_ticket(user)["client"]
        accounts.queue_action(user, "/leave", {"id": current["id"]})

    def test_admin_accounts_leave_client_queue_and_cannot_rejoin(self):
        user = {
            "id": "promoted-user",
            "name": "Manager",
            "verified": 1,
            "role": "client",
        }
        with accounts.connect() as db:
            db.execute(
                "INSERT INTO users(id,email,name,password,verified) VALUES(?,?,?,?,1)",
                (
                    user["id"],
                    "manager@example.test",
                    user["name"],
                    accounts.password_hash("Long test password 123"),
                ),
            )
        entry = accounts.queue_action(user, "/join", {"issue": "Software Issue"})
        accounts.set_admin("manager@example.test")
        user["role"] = "admin"
        self.assertEqual(accounts.status(user, entry["id"])["status"], "left")
        self.assertIsNone(accounts.own_ticket(user)["client"])
        with self.assertRaises(accounts.AppError) as error:
            accounts.queue_action(user, "/join", {"issue": "Software Issue"})
        self.assertEqual(error.exception.status, 403)
        with accounts.connect() as db:
            row = db.execute(
                "SELECT verified,role FROM users WHERE id=?", (user["id"],)
            ).fetchone()
        self.assertEqual(row["verified"], 1)
        self.assertEqual(row["role"], "admin")

    def test_full_flow_and_access_boundaries(self):
        adam, sarah, admin, guest = [self.browser() for _ in range(4)]
        self.assertEqual(self.request(guest, "/health")[1], {"status": "ok"})
        self.assertEqual(self.request(guest, "/queue")[0], 401)
        token = self.register(adam, "adam@example.test", "Adam")
        self.assertEqual(
            self.request(
                adam,
                "/auth/login",
                {"email": "adam@example.test", "password": "Long test password 123"},
            )[0],
            403,
        )
        self.assertEqual(self.request(adam, "/auth/verify", {"token": token})[0], 200)
        self.assertEqual(self.request(adam, "/auth/verify", {"token": token})[0], 400)
        a_csrf = self.login(adam, "adam@example.test")
        for b, email, name in [
            (sarah, "sarah@example.test", "Sarah"),
            (admin, "admin@example.test", "Admin"),
        ]:
            token = self.register(b, email, name)
            self.assertEqual(self.request(b, "/auth/verify", {"token": token})[0], 200)
        accounts.set_admin("admin@example.test")
        s_csrf = self.login(sarah, "sarah@example.test")
        admin_csrf = self.login(admin, "admin@example.test")
        self.assertEqual(self.request(adam, "/serve", {}, a_csrf)[0], 403)
        self.assertEqual(
            self.request(adam, "/join", {"issue": "Software Issue"})[0], 403
        )
        self.assertEqual(
            self.request(
                adam,
                "/join",
                {"issue": "Software Issue"},
                a_csrf,
                {"Origin": "https://attacker.example"},
            )[0],
            403,
        )
        _, a, _ = self.request(
            adam, "/join", {"issue": "Software Issue", "name": "Impersonated"}, a_csrf
        )
        self.assertEqual(a["name"], "Adam")
        _, s, _ = self.request(sarah, "/join", {"issue": "Email Issue"}, s_csrf)
        self.assertEqual(s["position"], 2)
        self.assertEqual(
            self.request(adam, "/join", {"issue": "Software Issue"}, a_csrf)[0], 409
        )
        self.assertEqual(self.request(sarah, "/leave", {"id": a["id"]}, s_csrf)[0], 404)
        self.assertEqual(self.request(sarah, "/status/" + a["id"])[0], 404)
        self.assertEqual(
            self.request(sarah, "/queue")[1]["queue"][0]["issue"], "IT support"
        )
        self.assertEqual(
            self.request(admin, "/queue")[1]["queue"][0]["issue"], "Software Issue"
        )
        accounts.initialize()  # Reopening the database preserves records.
        self.assertEqual(self.request(adam, "/my-ticket")[1]["client"]["id"], a["id"])
        self.assertEqual(
            self.request(admin, "/serve", {}, admin_csrf)[1]["id"], a["id"]
        )
        self.assertEqual(
            self.request(adam, "/my-ticket")[1]["client"]["status"], "served"
        )
        self.request(adam, "/acknowledge", {"id": a["id"]}, a_csrf)
        self.assertIsNone(self.request(adam, "/my-ticket")[1]["client"])
        self.assertEqual(self.request(sarah, "/status/" + s["id"])[1]["position"], 1)
        self.assertEqual(self.request(sarah, "/leave", {"id": s["id"]}, s_csrf)[0], 200)
        self.assertEqual(self.request(admin, "/serve", {}, admin_csrf)[0], 409)
        self.assertEqual(
            self.request(adam, "/auth/forgot", {"email": "adam@example.test"})[0], 200
        )
        reset = self.link("adam@example.test", "reset")
        with accounts.connect() as db:
            db.execute(
                "UPDATE links SET expires=0 WHERE hash=?", (accounts.digest(reset),)
            )
        self.assertEqual(
            self.request(
                adam,
                "/auth/reset",
                {"token": reset, "password": "New long password 456"},
            )[0],
            400,
        )
        self.request(adam, "/auth/forgot", {"email": "adam@example.test"})
        reset = self.link("adam@example.test", "reset")
        self.assertEqual(
            self.request(
                adam,
                "/auth/reset",
                {"token": reset, "password": "New long password 456"},
            )[0],
            200,
        )
        self.assertEqual(self.request(adam, "/queue")[0], 401)
        self.assertEqual(
            self.request(
                adam,
                "/auth/reset",
                {"token": reset, "password": "New long password 456"},
            )[0],
            400,
        )
        a_csrf = self.login(adam, "adam@example.test", "New long password 456")
        self.assertEqual(self.request(adam, "/auth/logout", {}, a_csrf)[0], 200)
        self.assertEqual(self.request(adam, "/queue")[0], 401)
        with accounts.connect() as db:
            row = db.execute(
                "SELECT password FROM users WHERE email=?", ("adam@example.test",)
            ).fetchone()
            self.assertNotIn("New long password", row["password"])
        for _ in range(2):
            accounts.limited("test-rate", maximum=2)
        with self.assertRaises(accounts.AppError):
            accounts.limited("test-rate", maximum=2)
        os.environ.pop("QUEUE_EMAIL_MODE")
        saved = {k: os.environ.pop(k, None) for k in ("SMTP_HOST", "SMTP_FROM")}
        try:
            self.assertEqual(
                self.request(
                    guest,
                    "/auth/register",
                    {
                        "email": "blocked@example.test",
                        "name": "Blocked",
                        "password": "Long test password 123",
                    },
                )[0],
                503,
            )
        finally:
            os.environ["QUEUE_EMAIL_MODE"] = "file"
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v


if __name__ == "__main__":
    unittest.main()
