import argparse
import json
import os
import secrets
import webbrowser
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Timer
from urllib.parse import urlsplit
import accounts


class QueueRequestHandler(BaseHTTPRequestHandler):
    def handle(self):
        try:
            super().handle()
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            # A closed tab or temporary disconnect needs no error response.
            pass

    def log_message(self, format, *args):
        # Do not log request bodies or verification/reset tokens.
        pass

    def headers_common(self):
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            "default-src 'self'; script-src 'self'; style-src 'self'; connect-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'none'",
        )

    def send_json(self, data, status=200, cookie=None):
        payload = json.dumps(data).encode()
        self.send_response(status)
        self.headers_common()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()
        self.wfile.write(payload)

    def token(self):
        cookie = SimpleCookie()
        try:
            cookie.load(self.headers.get("Cookie", ""))
        except Exception:
            return None
        return cookie["queue_session"].value if "queue_session" in cookie else None

    def cookie(self, token, clear=False):
        secure = "; Secure" if accounts.BASE_URL.startswith("https://") else ""
        return f"queue_session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={0 if clear else 43200}{secure}"

    def send_page(self, filename, content_type):
        payload = (Path(__file__).parent / "web" / filename).read_bytes()
        self.send_response(200)
        self.headers_common()
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        try:
            path = urlsplit(self.path).path
            pages = {
                "/": "index.html",
                "/admin": "index.html",
                "/verify": "index.html",
                "/reset": "index.html",
                "/style.css": "style.css",
                "/app.js": "app.js",
            }
            if path in pages:
                kind = (
                    "text/css"
                    if path.endswith(".css")
                    else "text/javascript" if path.endswith(".js") else "text/html"
                )
                self.send_page(pages[path], kind + "; charset=utf-8")
                return
            if path == "/health":
                with accounts.connect() as db:
                    db.execute("SELECT 1").fetchone()
                self.send_json({"status": "ok"})
                return
            user = accounts.session(self.token())
            if path == "/auth/me":
                self.send_json(
                    {
                        "user": accounts.public_user(user) if user else None,
                        "csrf": user["csrf"] if user else None,
                        "development_mail": os.environ.get("QUEUE_EMAIL_MODE")
                        == "file",
                    }
                )
                return
            if path == "/queue":
                result = accounts.queue_list(user)
            elif path == "/my-ticket":
                result = accounts.own_ticket(user)
            elif path == "/history":
                result = accounts.history_list(user)
            elif path.startswith("/status/"):
                result = accounts.status(user, path[len("/status/") :])
            else:
                raise accounts.AppError("Page not found.", 404)
            self.send_json(result)
        except accounts.AppError as error:
            self.send_json({"error": str(error)}, error.status)

    def do_POST(self):
        try:
            path = urlsplit(self.path).path
            # All writes require same-origin JSON requests.
            origin = self.headers.get("Origin")
            configured = urlsplit(accounts.BASE_URL)
            allowed = {
                configured.scheme + "://" + configured.netloc,
                "http://" + self.headers.get("Host", ""),
            }
            if origin and origin not in allowed:
                raise accounts.AppError("Request origin is not allowed.", 403)
            if self.headers.get("Sec-Fetch-Site") == "cross-site":
                raise accounts.AppError("Cross-site request blocked.", 403)
            if (
                self.headers.get("Content-Type", "").split(";")[0].strip()
                != "application/json"
            ):
                raise accounts.AppError("Send JSON requests.", 415)
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                raise accounts.AppError("Invalid request size.")
            if not 0 < length <= 8192:
                raise accounts.AppError("Invalid request size.")
            try:
                data = json.loads(self.rfile.read(length))
            except (ValueError, UnicodeError):
                raise accounts.AppError("Invalid JSON.")
            if not isinstance(data, dict):
                raise accounts.AppError("Expected a JSON object.")
            user = accounts.session(self.token())
            if path.startswith("/auth/"):
                accounts.limited(self.client_address[0] + ":" + path, maximum=30)
                if path in (
                    "/auth/login",
                    "/auth/register",
                    "/auth/resend",
                    "/auth/forgot",
                ):
                    address = data.get("email", "")
                    if isinstance(address, str):
                        accounts.limited(
                            path + ":" + address.strip().lower(), maximum=8
                        )
                if path == "/auth/register":
                    result = accounts.register(data)
                elif path == "/auth/login":
                    result, token = accounts.login(data)
                    self.send_json(result, cookie=self.cookie(token))
                    return
                elif path == "/auth/verify":
                    result = accounts.consume_link(data, "verify")
                elif path == "/auth/reset":
                    result = accounts.consume_link(data, "reset")
                elif path == "/auth/resend":
                    result = accounts.request_link(data, "verify")
                elif path == "/auth/forgot":
                    result = accounts.request_link(data, "reset")
                elif path == "/auth/logout":
                    accounts.require_user(user)
                    self.check_csrf(user)
                    with accounts.connect() as db:
                        db.execute(
                            "DELETE FROM sessions WHERE hash=?",
                            (accounts.digest(self.token()),),
                        )
                    self.send_json(
                        {"message": "Signed out"}, cookie=self.cookie("", True)
                    )
                    return
                else:
                    raise accounts.AppError("Page not found.", 404)
            elif path in ("/join", "/leave", "/serve", "/acknowledge", "/update", "/cancel"):
                accounts.require_user(user)
                self.check_csrf(user)
                result = accounts.queue_action(user, path, data)
            else:
                raise accounts.AppError("Page not found.", 404)
            self.send_json(result, 201 if path in ("/join", "/auth/register") else 200)
        except accounts.AppError as error:
            self.send_json({"error": str(error)}, error.status)
        except Exception:
            self.send_json(
                {"error": "The request could not be completed. Please try again."}, 500
            )

    def check_csrf(self, user):
        if not secrets.compare_digest(
            self.headers.get("X-CSRF-Token", ""), user["csrf"]
        ):
            raise accounts.AppError("Please refresh the page and try again.", 403)


def open_browser_pages():
    for path in ("/", "/admin"):
        webbrowser.open_new_tab(accounts.BASE_URL + path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verified-account IT queue server")
    parser.add_argument(
        "--make-admin",
        metavar="EMAIL",
        help="Grant admin to an already verified account",
    )
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    accounts.initialize()
    if args.make_admin:
        try:
            accounts.set_admin(args.make_admin)
            print("Admin access assigned. Sign in again to use it.")
        except accounts.AppError as error:
            parser.error(str(error))
    else:
        bind = os.environ.get("QUEUE_HOST", "127.0.0.1")
        port = int(os.environ.get("QUEUE_PORT", os.environ.get("PORT", "8000")))
        if not accounts.BASE_URL.startswith("https://") and bind not in (
            "127.0.0.1",
            "localhost",
        ):
            parser.error(
                "Account sign-in requires HTTPS outside local testing. Set QUEUE_BASE_URL to your HTTPS site URL."
            )
        server = ThreadingHTTPServer((bind, port), QueueRequestHandler)
        print("Client: " + accounts.BASE_URL + "/")
        print("Admin: " + accounts.BASE_URL + "/admin")
        print(
            "Email mode: "
            + (
                "local development files (no emails sent)"
                if os.environ.get("QUEUE_EMAIL_MODE") == "file"
                else "SMTP"
            )
        )
        timer = None
        if not args.no_browser:
            timer = Timer(0.5, open_browser_pages)
            timer.daemon = True
            timer.start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            if timer:
                timer.cancel()
            server.server_close()
