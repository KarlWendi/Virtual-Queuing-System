"""Configure private Gmail settings on the hosting account, not on GitHub."""

import getpass
import json
import os
import re
import smtplib
import ssl
from pathlib import Path


def main():
    print("Run this in a PythonAnywhere Bash console after cloning the project.")
    site = input("Your full HTTPS PythonAnywhere site URL: ").strip().rstrip("/")
    if not re.fullmatch(r"https://[A-Za-z0-9-]+\.(?:eu\.)?pythonanywhere\.com", site):
        raise SystemExit(
            "Enter the HTTPS site URL shown on your PythonAnywhere Web tab."
        )
    email = input("Sending Gmail address: ").strip().lower()
    if not re.fullmatch(r"[^\s@]+@gmail\.com", email):
        raise SystemExit("Enter your Gmail sending address.")
    password = getpass.getpass("Google app password (hidden): ").replace(" ", "")
    if not re.fullmatch(r"[A-Za-z0-9]{16}", password):
        raise SystemExit("Enter the 16-character Google app password.")
    try:
        with smtplib.SMTP_SSL(
            "smtp.gmail.com", 465, timeout=20, context=ssl.create_default_context()
        ) as smtp:
            smtp.login(email, password)
            smtp.noop()
    except (OSError, smtplib.SMTPException):
        raise SystemExit(
            "Gmail is not reachable or rejected authentication from this host. No settings were saved."
        )
    config = {
        "QUEUE_BASE_URL": site,
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_PORT": "465",
        "SMTP_USERNAME": email,
        "SMTP_PASSWORD": password,
        "SMTP_FROM": email,
    }
    path = Path(__file__).parent / "data" / "hosting.json"
    path.parent.mkdir(exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.chmod(path, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(config, output)
    except Exception:
        path.unlink(missing_ok=True)
        raise
    print(
        "Gmail connection verified. Private settings saved under data/, excluded from Git."
    )
    print(
        "Reload the web app and test registration email delivery before sharing its URL."
    )


if __name__ == "__main__":
    main()
