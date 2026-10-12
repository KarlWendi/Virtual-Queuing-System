"""Start the local queue with Gmail delivery; credentials remain in memory."""

import argparse
import getpass
import os
import re
import runpy
import smtplib
import socket
import ssl
from email.message import EmailMessage
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Start the queue with real Gmail email delivery"
    )
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Choose a port between 1 and 65535.")

    # Check the selected port before requesting credentials or sending email.
    try:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", args.port))
    except OSError:
        parser.error(
            f"Port {args.port} is already in use. Stop its server or choose --port 8004."
        )

    print("Gmail delivery setup")
    print("Enable Google 2-Step Verification, then create an app password:")
    print("https://myaccount.google.com/apppasswords")
    print("The app password is entered privately and is not saved to a file.")
    print("This setup sends one delivery test email to your own Gmail address.")
    email = input("Sending Gmail address: ").strip().lower()
    if not re.fullmatch(r"[^\s@]+@gmail\.com", email):
        parser.error(
            "Enter your personal @gmail.com address for this Gmail test launcher."
        )
    password = getpass.getpass("Google app password (hidden): ").replace(" ", "")
    if not re.fullmatch(r"[A-Za-z0-9]{16}", password):
        parser.error(
            "Enter the 16-character app password, not your regular Google password."
        )

    message = EmailMessage()
    message["From"] = email
    message["To"] = email
    message["Subject"] = "IT Help Desk: email delivery test"
    message.set_content(
        "Your IT Help Desk queue can now send email through Gmail.\n\n"
        "Next, create an account in the queue app with this email address. "
        "You will receive a separate verification email.\n\n"
        "This message was requested by the local Gmail setup launcher."
    )
    try:
        with smtplib.SMTP_SSL(
            "smtp.gmail.com", 465, timeout=20, context=ssl.create_default_context()
        ) as smtp:
            smtp.login(email, password)
            refused = smtp.send_message(message)
            if refused:
                parser.error("Gmail did not accept the delivery test recipient.")
    except smtplib.SMTPAuthenticationError:
        parser.error(
            "Gmail rejected the sign-in. Check the address, 2-Step Verification, and app password."
        )
    except (OSError, smtplib.SMTPException):
        parser.error(
            "Could not connect to Gmail or send the test message. Check your connection and try again."
        )

    print("Gmail accepted the test message. Check your inbox and spam folder.")
    print("Real verification and password-reset email delivery is now enabled.")
    print(
        "Local email links work on this computer; online use still requires HTTPS hosting."
    )
    settings = {
        "SMTP_HOST": "smtp.gmail.com",
        "SMTP_PORT": "465",
        "SMTP_USERNAME": email,
        "SMTP_PASSWORD": password,
        "SMTP_FROM": email,
        "QUEUE_HOST": "127.0.0.1",
        "QUEUE_PORT": str(args.port),
        "QUEUE_BASE_URL": f"http://127.0.0.1:{args.port}",
    }
    old = {key: os.environ.get(key) for key in settings}
    old_mode = os.environ.pop("QUEUE_EMAIL_MODE", None)
    os.environ.update(settings)
    import sys

    old_argv = sys.argv[:]
    sys.argv = ["server.py"] + (["--no-browser"] if args.no_browser else [])
    try:
        runpy.run_path(str(Path(__file__).parent / "server.py"), run_name="__main__")
    finally:
        sys.argv = old_argv
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        if old_mode is not None:
            os.environ["QUEUE_EMAIL_MODE"] = old_mode


if __name__ == "__main__":
    main()
