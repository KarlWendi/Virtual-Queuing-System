"""Real-browser checks against an isolated database and local development mailbox."""

import json
import os
import tempfile
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from playwright.sync_api import sync_playwright, expect
import accounts
import server

PASSWORD = "A long test password 123"


def main():
    with tempfile.TemporaryDirectory() as directory:
        accounts.DB_PATH = Path(directory) / "test.sqlite3"
        os.environ["QUEUE_EMAIL_MODE"] = "file"
        accounts.initialize()
        app = server.ThreadingHTTPServer(("127.0.0.1", 0), server.QueueRequestHandler)
        accounts.BASE_URL = f"http://127.0.0.1:{app.server_port}"
        thread = threading.Thread(target=app.serve_forever, daemon=True)
        thread.start()
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(
                    executable_path=r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                    headless=True,
                )
                contexts = []
                errors = []

                def make_page(width=1280):
                    context = browser.new_context(
                        viewport={"width": width, "height": 900}
                    )
                    contexts.append(context)
                    page = context.new_page()
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    return page

                def newest_link(email, kind):
                    paths = sorted(
                        (accounts.DB_PATH.parent / "dev-mail").glob("*.json"),
                        key=lambda p: p.stat().st_mtime_ns,
                        reverse=True,
                    )
                    prefix = "Verify" if kind == "verify" else "Reset"
                    for path in paths:
                        data = json.loads(path.read_text(encoding="utf-8"))
                        if data["to"] == email and data["subject"].startswith(prefix):
                            return (
                                data["text"]
                                .split("Open this link: ")[1]
                                .splitlines()[0]
                            )
                    raise AssertionError("Missing test email")

                def register(page, name, email):
                    page.goto(accounts.BASE_URL)
                    expect(page.locator(".intro p")).to_contain_text("we\u2019ll")
                    expect(page.locator("#join-button")).to_contain_text("\u2192")
                    page.locator("#show-register").click()
                    page.locator("#auth-name").fill(name)
                    page.locator("#auth-email").fill(email)
                    page.locator("#auth-password").fill(PASSWORD)
                    page.locator("#auth-submit").click()
                    expect(page.locator("#message")).to_contain_text("Check your email")
                    # Unverified accounts must not enter the queue.
                    page.locator("#show-login").click()
                    page.locator("#auth-email").fill(email)
                    page.locator("#auth-password").fill(PASSWORD)
                    page.locator("#auth-submit").click()
                    expect(page.locator("#message")).to_contain_text(
                        "Verify your email"
                    )
                    page.locator("#show-resend").click()
                    page.locator("#auth-submit").click()
                    expect(page.locator("#message")).to_contain_text(
                        "email has been sent"
                    )
                    page.goto(newest_link(email, "verify"))
                    expect(page.locator("#auth-title")).to_have_text(
                        "Confirm your email"
                    )
                    assert page.evaluate("location.hash") == ""
                    page.locator("#auth-submit").click()
                    expect(page.locator("#auth-title")).to_have_text("Sign in")

                def login(page, email, password=PASSWORD):
                    page.locator("#auth-email").fill(email)
                    page.locator("#auth-password").fill(password)
                    page.locator("#auth-submit").click()
                    expect(page.locator("#queue-panel")).to_be_visible()

                adam, sarah, administrator = [make_page() for _ in range(3)]
                register(adam, "Adam", "adam@example.test")
                register(sarah, "Sarah", "sarah@example.test")
                register(administrator, "Admin", "admin@example.test")
                accounts.set_admin("admin@example.test")
                login(adam, "adam@example.test")
                login(sarah, "sarah@example.test")
                login(administrator, "admin@example.test")
                administrator.goto(accounts.BASE_URL + "/admin")
                expect(administrator.locator("#admin-controls")).to_be_visible()
                adam.locator("#issue").select_option("Software Issue")
                adam.locator("#join-button").click()
                expect(adam.locator("#position")).to_have_text("1")
                sarah.locator("#issue").select_option("Email Issue")
                sarah.locator("#join-button").click()
                expect(sarah.locator("#position")).to_have_text("2")
                expect(sarah.locator("#ahead")).to_have_text("1")
                adam.reload()
                expect(adam.locator("#ticket")).to_be_visible()
                expect(adam.locator("#position")).to_have_text("1")
                expect(administrator.locator("#count")).to_have_text("2 waiting")
                administrator.locator("#serve-button").click()
                expect(adam.locator("#turn-dialog")).to_be_visible(timeout=10000)
                expect(adam.locator("#turn-title")).to_contain_text("Adam")
                adam.locator("#dismiss-turn").click()
                expect(adam.locator("#turn-dialog")).not_to_be_visible()
                adam.reload()
                expect(adam.locator("#join-form")).to_be_visible()
                expect(adam.locator("#turn-dialog")).not_to_be_visible()
                expect(sarah.locator("#position")).to_have_text("1", timeout=10000)
                sarah.locator("#leave-button").click()
                expect(sarah.locator("#join-form")).to_be_visible()
                expect(administrator.locator("#count")).to_have_text(
                    "0 waiting", timeout=10000
                )
                administrator.locator("#serve-button").click()
                expect(administrator.locator("#message")).to_contain_text(
                    "nobody waiting"
                )
                # Both UI and server deny clients administrator privileges.
                sarah.goto(accounts.BASE_URL + "/admin")
                expect(sarah.locator("#auth-description")).to_contain_text(
                    "does not have administrator access"
                )
                expect(sarah.locator("#admin-controls")).not_to_be_visible()
                csrf = sarah.evaluate("csrf")
                response = sarah.context.request.post(
                    accounts.BASE_URL + "/serve",
                    data={},
                    headers={"X-CSRF-Token": csrf},
                )
                assert response.status == 403
                # Recovery form and link complete a real password reset.
                adam.locator("#sign-out").click()
                expect(adam.locator("#account-panel")).to_be_visible()
                adam.locator("#show-forgot").click()
                adam.locator("#auth-email").fill("adam@example.test")
                adam.locator("#auth-submit").click()
                expect(adam.locator("#message")).to_contain_text("email has been sent")
                adam.goto(newest_link("adam@example.test", "reset"))
                expect(adam.locator("#auth-title")).to_have_text(
                    "Choose a new password"
                )
                adam.locator("#auth-password").fill("A different long password 456")
                adam.locator("#auth-submit").click()
                expect(adam.locator("#auth-title")).to_have_text("Sign in")
                login(adam, "adam@example.test", "A different long password 456")
                # Responsive account and queue pages.
                phone = make_page(390)
                phone.goto(accounts.BASE_URL)
                expect(phone.locator("#auth-form")).to_be_visible()
                assert phone.evaluate(
                    "document.documentElement.scrollWidth <= innerWidth"
                ), "Mobile page overflows horizontally"
                phone.locator("#auth-email").fill("adam@example.test")
                phone.locator("#auth-password").fill("A different long password 456")
                phone.locator("#auth-submit").click()
                expect(phone.locator("#queue-panel")).to_be_visible()
                assert phone.evaluate(
                    "document.documentElement.scrollWidth <= innerWidth"
                ), "Signed-in mobile page overflows"
                # Temporary offline recovery.
                phone.context.set_offline(True)
                phone.evaluate("poll()")
                expect(phone.locator("#connection")).to_contain_text(
                    "interrupted", timeout=10000
                )
                phone.context.set_offline(False)
                expect(phone.locator("#connection")).to_contain_text(
                    "Live", timeout=10000
                )
                folder = Path(".test-results")
                folder.mkdir(exist_ok=True)
                phone.screenshot(path=str(folder / "mobile.png"), full_page=True)
                administrator.screenshot(path=str(folder / "admin.png"), full_page=True)
                assert not errors, errors
                for context in contexts:
                    context.close()
                browser.close()
                print(
                    "PASS: real-browser registration, blocked unverified login, resend, verification, login, queue order, refresh recovery, admin serving, turn notification, acknowledgement, leaving, permissions, password reset, phone layout, and offline recovery."
                )
        finally:
            app.shutdown()
            app.server_close()
            thread.join()


if __name__ == "__main__":
    main()
