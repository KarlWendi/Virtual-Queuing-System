"""Persistent accounts, sessions, email links, and owned queue records."""

import hashlib
import hmac
import json
import os
import re
import secrets
import smtplib
import sqlite3
import ssl
import time
from email.message import EmailMessage
from pathlib import Path

DB_PATH = Path(
    os.environ.get("QUEUE_DB", str(Path(__file__).parent / "data" / "queue.sqlite3"))
)
BASE_URL = os.environ.get(
    "QUEUE_BASE_URL",
    os.environ.get("RENDER_EXTERNAL_URL", "http://127.0.0.1:8000"),
).rstrip("/")
ADMIN_SECRET_KEY = os.environ.get("ADMIN_SECRET_KEY", "admin-secret-123")
ISSUES = [
    "Password / Account Issue",
    "Wi-Fi / Network Issue",
    "Software Issue",
    "Hardware Issue",
    "Printing Issue",
    "Email Issue",
    "Other",
]


class AppError(Exception):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


# DATABASE CONNECTIONS


class DatabaseConnection(sqlite3.Connection):
    def __exit__(self, *args):
        try:
            return super().__exit__(*args)
        finally:
            self.close()


def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(DB_PATH, timeout=10, factory=DatabaseConnection)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys=ON")
    return db


def initialize():
    with connect() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,name TEXT NOT NULL,password TEXT NOT NULL,verified INTEGER NOT NULL DEFAULT 0,role TEXT NOT NULL DEFAULT 'client',admin_pin TEXT);
        CREATE TABLE IF NOT EXISTS sessions(hash TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),expires INTEGER NOT NULL,csrf TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS links(hash TEXT PRIMARY KEY,user_id TEXT NOT NULL REFERENCES users(id),kind TEXT NOT NULL,expires INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS entries(seq INTEGER PRIMARY KEY AUTOINCREMENT,id TEXT UNIQUE NOT NULL,user_id TEXT NOT NULL REFERENCES users(id),name TEXT NOT NULL,issue TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'waiting',notified INTEGER NOT NULL DEFAULT 0);
        CREATE UNIQUE INDEX IF NOT EXISTS one_waiting_per_user ON entries(user_id) WHERE status='waiting';
        CREATE TABLE IF NOT EXISTS limits(key TEXT PRIMARY KEY,count INTEGER NOT NULL,expires INTEGER NOT NULL);
        """)
        columns = [row[1] for row in db.execute("PRAGMA table_info(users)").fetchall()]
        if "admin_pin" not in columns:
            db.execute("ALTER TABLE users ADD COLUMN admin_pin TEXT")


# PASSWORDS AND REQUEST LIMITS


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(password):
    if not isinstance(password, str) or not 12 <= len(password) <= 256:
        raise AppError("Use a password between 12 and 256 characters.")
    salt = secrets.token_hex(16)
    result = hashlib.scrypt(
        password.encode(),
        salt=bytes.fromhex(salt),
        n=32768,
        r=8,
        p=1,
        maxmem=64 * 1024 * 1024,
    )
    return salt + ":" + result.hex()


def password_matches(password, stored):
    if not isinstance(password, str) or len(password) > 256:
        return False
    salt, expected = stored.split(":")
    actual = hashlib.scrypt(
        password.encode(),
        salt=bytes.fromhex(salt),
        n=32768,
        r=8,
        p=1,
        maxmem=64 * 1024 * 1024,
    ).hex()
    return hmac.compare_digest(actual, expected)


def email_address(value):
    if (
        not isinstance(value, str)
        or len(value) > 254
        or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value)
    ):
        raise AppError("Enter a valid email address.")
    return value.strip().lower()


def limited(key, maximum=8, duration=900):
    now = int(time.time())
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute("SELECT * FROM limits WHERE key=?", (digest(key),)).fetchone()
        if row and row["expires"] > now and row["count"] >= maximum:
            raise AppError("Too many attempts. Please try again later.", 429)
        count = row["count"] + 1 if row and row["expires"] > now else 1
        expires = row["expires"] if row and row["expires"] > now else now + duration
        db.execute(
            "INSERT OR REPLACE INTO limits VALUES(?,?,?)", (digest(key), count, expires)
        )


# EMAIL VERIFICATION AND RESET LINKS


def mail_ready():
    if os.environ.get("QUEUE_EMAIL_MODE") == "file":
        return
    if not os.environ.get("SMTP_HOST") or not os.environ.get("SMTP_FROM"):
        raise AppError(
            "Email delivery is not configured yet. Please contact the administrator.",
            503,
        )


def send_email(address, kind, token=None):
    mail_ready()
    if kind == "served":
        subject = "It's your turn at the IT Help Desk!"
        text = f"Hello,\n\nIt is now your turn! Please proceed to the IT Help Desk.\n\nThank you,\nIT Help Desk Team"
    else:
        url = BASE_URL + ("/verify" if kind == "verify" else "/reset") + "#token=" + (token or "")
        subject = (
            "Verify your IT Help Desk account"
            if kind == "verify"
            else "Reset your IT Help Desk password"
        )
        text = f"{subject}\n\nOpen this link: {url}\n\nThis link expires in {'24 hours' if kind=='verify' else '30 minutes'} and can be used once. If you did not request it, you can ignore this email."
    if os.environ.get("QUEUE_EMAIL_MODE") == "file":
        folder = DB_PATH.parent / "dev-mail"
        folder.mkdir(exist_ok=True)
        (folder / (secrets.token_hex(12) + ".json")).write_text(
            json.dumps({"to": address, "subject": subject, "text": text}),
            encoding="utf-8",
        )
        return
    msg = EmailMessage()
    msg["From"] = os.environ["SMTP_FROM"]
    msg["To"] = address
    msg["Subject"] = subject
    msg.set_content(text)
    port = int(os.environ.get("SMTP_PORT", "587"))
    try:
        if port == 465:
            smtp = smtplib.SMTP_SSL(
                os.environ["SMTP_HOST"],
                port,
                timeout=15,
                context=ssl.create_default_context(),
            )
        else:
            smtp = smtplib.SMTP(os.environ["SMTP_HOST"], port, timeout=15)
            smtp.starttls(context=ssl.create_default_context())
        with smtp:
            if os.environ.get("SMTP_USERNAME"):
                smtp.login(
                    os.environ["SMTP_USERNAME"], os.environ.get("SMTP_PASSWORD", "")
                )
            smtp.send_message(msg)
    except (OSError, smtplib.SMTPException):
        raise AppError("The email could not be sent. Please try again later.", 503)


def issue_link(user_id, address, kind):
    token = secrets.token_urlsafe(32)
    with connect() as db:
        db.execute("DELETE FROM links WHERE user_id=? AND kind=?", (user_id, kind))
        db.execute(
            "INSERT INTO links VALUES(?,?,?,?)",
            (
                digest(token),
                user_id,
                kind,
                int(time.time()) + (86400 if kind == "verify" else 1800),
            ),
        )
    try:
        send_email(address, kind, token)
    except AppError:
        with connect() as db:
            db.execute("DELETE FROM links WHERE hash=?", (digest(token),))
        raise


# ACCOUNTS AND SIGN-IN


def public_user(row):
    return {key: row[key] for key in ("id", "email", "name", "role", "verified")}


def session(token):
    if not token:
        return None
    with connect() as db:
        row = db.execute(
            "SELECT users.*,sessions.csrf FROM sessions JOIN users ON users.id=sessions.user_id WHERE sessions.hash=? AND sessions.expires>?",
            (digest(token), int(time.time())),
        ).fetchone()
    return dict(row) if row else None


def register(data):
    mail_ready()
    email = email_address(data.get("email"))
    name = data.get("name")
    if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
        raise AppError("Enter a name between 1 and 100 characters.")
    hashed = password_hash(data.get("password"))
    with connect() as db:
        existing = db.execute("SELECT id FROM users WHERE email=?", (email,)).fetchone()
        if existing:
            return {
                "message": "If this address can be registered, a verification email has been sent. Otherwise, sign in or reset your password."
            }
        user_id = secrets.token_hex(16)
        db.execute(
            "INSERT INTO users(id,email,name,password) VALUES(?,?,?,?)",
            (user_id, email, name.strip(), hashed),
        )
    issue_link(user_id, email, "verify")
    return {
        "message": "Check your email for the verification link. Verify your address before signing in."
    }


def validate_pin_format(pin):
    if not isinstance(pin, str) or not pin.isdigit() or not (4 <= len(pin) <= 8):
        raise AppError("Enter a valid numeric PIN between 4 and 8 digits.")

def pin_hash(pin):
    validate_pin_format(pin)
    salt = secrets.token_hex(16)
    result = hashlib.scrypt(
        pin.encode(),
        salt=bytes.fromhex(salt),
        n=32768,
        r=8,
        p=1,
        maxmem=64 * 1024 * 1024,
    )
    return salt + ":" + result.hex()

def login(data):
    email = email_address(data.get("email"))
    with connect() as db:
        row = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    # An unknown account still incurs password hashing work.
    stored = row["password"] if row else password_hash("constant-dummy-password")
    valid = password_matches(data.get("password"), stored)
    if not row or not valid:
        raise AppError("Email or password is incorrect.", 401)
    if not row["verified"]:
        raise AppError(
            "Verify your email before signing in. You can request another verification link.",
            403,
        )
    if row["role"] == "admin":
        pin = data.get("pin")
        if not pin or not row["admin_pin"] or not password_matches(str(pin), row["admin_pin"]):
            raise AppError("Valid Admin PIN is required for administrator sign in.", 401)
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    with connect() as db:
        db.execute("DELETE FROM sessions WHERE expires<=?", (int(time.time()),))
        db.execute(
            "INSERT INTO sessions VALUES(?,?,?,?)",
            (digest(token), row["id"], int(time.time()) + 43200, csrf),
        )
    return {"user": public_user(row), "csrf": csrf}, token

def claim_admin(user, data):
    require_user(user)
    secret_key = data.get("secret_key")
    pin = data.get("pin")
    if not isinstance(secret_key, str) or not secrets.compare_digest(secret_key, ADMIN_SECRET_KEY):
        raise AppError("Invalid Admin Secret Key.", 403)
    validate_pin_format(pin)
    hashed_pin = pin_hash(str(pin))
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        db.execute(
            "UPDATE users SET role='admin', admin_pin=? WHERE id=?",
            (hashed_pin, user["id"]),
        )
        db.execute(
            "UPDATE entries SET status='left', notified=1 WHERE user_id=? AND status='waiting'",
            (user["id"],),
        )
        db.execute(
            "UPDATE entries SET notified=1 WHERE user_id=? AND status='served'",
            (user["id"],),
        )
        row = db.execute("SELECT * FROM users WHERE id=?", (user["id"],)).fetchone()
    return {"message": "Admin status claimed successfully. Please sign in with your email, password, and PIN.", "user": public_user(row)}


def request_link(data, kind):
    mail_ready()
    email = email_address(data.get("email"))
    with connect() as db:
        row = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
    if row and (
        (kind == "verify" and not row["verified"])
        or (kind == "reset" and row["verified"])
    ):
        issue_link(row["id"], email, kind)
    return {
        "message": "If an eligible account exists, an email has been sent. Check your inbox."
    }


def consume_link(data, kind):
    token = data.get("token")
    if not isinstance(token, str) or len(token) > 200:
        raise AppError("Invalid or expired link.")
    hashed = password_hash(data.get("password")) if kind == "reset" else None
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        row = db.execute(
            "SELECT * FROM links WHERE hash=? AND kind=? AND expires>?",
            (digest(token), kind, int(time.time())),
        ).fetchone()
        if not row:
            raise AppError("Invalid or expired link. Please request a new email.")
        if kind == "verify":
            db.execute("UPDATE users SET verified=1 WHERE id=?", (row["user_id"],))
        else:
            db.execute(
                "UPDATE users SET password=? WHERE id=?", (hashed, row["user_id"])
            )
            db.execute("DELETE FROM sessions WHERE user_id=?", (row["user_id"],))
        db.execute(
            "DELETE FROM links WHERE user_id=? AND kind=?", (row["user_id"], kind)
        )
    return {
        "message": (
            "Email verified. You can now sign in."
            if kind == "verify"
            else "Password reset. Please sign in with your new password."
        )
    }


# QUEUE OWNERSHIP AND ADMIN ACCESS


def require_user(user, admin=False):
    if not user:
        raise AppError("Please sign in.", 401)
    if not user["verified"]:
        raise AppError("Please verify your email.", 403)
    if admin and user["role"] != "admin":
        raise AppError("Administrator access is required.", 403)


def queue_list(user):
    require_user(user)
    with connect() as db:
        rows = db.execute(
            "SELECT * FROM entries WHERE status='waiting' ORDER BY seq"
        ).fetchall()
    return {
        "queue": [
            {
                "id": r["id"],
                "name": r["name"],
                "issue": (
                    r["issue"]
                    if user["role"] == "admin" or r["user_id"] == user["id"]
                    else "IT support"
                ),
                "position": i,
                "people_ahead": i - 1,
            }
            for i, r in enumerate(rows, 1)
        ]
    }


def ticket(row, db):
    position = (
        db.execute(
            "SELECT COUNT(*) FROM entries WHERE status='waiting' AND seq<=?",
            (row["seq"],),
        ).fetchone()[0]
        if row["status"] == "waiting"
        else None
    )
    return {
        "id": row["id"],
        "name": row["name"],
        "issue": row["issue"],
        "status": row["status"],
        "position": position,
        "people_ahead": position - 1 if position else None,
    }


def own_ticket(user):
    require_user(user)
    with connect() as db:
        row = db.execute(
            "SELECT * FROM entries WHERE user_id=? AND (status='waiting' OR (status='served' AND notified=0)) ORDER BY seq DESC LIMIT 1",
            (user["id"],),
        ).fetchone()
        return {"client": ticket(row, db) if row else None}


def status(user, entry_id):
    require_user(user)
    with connect() as db:
        row = db.execute("SELECT * FROM entries WHERE id=?", (entry_id,)).fetchone()
        if not row or (row["user_id"] != user["id"] and user["role"] != "admin"):
            raise AppError("Client not found.", 404)
        return ticket(row, db)


def queue_action(user, path, data):
    require_user(user, admin=path == "/serve")
    if path == "/join" and user["role"] == "admin":
        raise AppError(
            "Administrator accounts manage the queue and cannot join as clients.", 403
        )
    with connect() as db:
        db.execute("BEGIN IMMEDIATE")
        if path == "/join":
            issue = data.get("issue")
            if issue not in ISSUES:
                raise AppError("Select an IT support issue.")
            if db.execute(
                "SELECT 1 FROM entries WHERE user_id=? AND status='waiting'",
                (user["id"],),
            ).fetchone():
                raise AppError("You are already in the queue.", 409)
            # Joining acknowledges any previous turn notice.
            db.execute(
                "UPDATE entries SET notified=1 WHERE user_id=? AND status='served'",
                (user["id"],),
            )
            entry_id = secrets.token_hex(16)
            db.execute(
                "INSERT INTO entries(id,user_id,name,issue) VALUES(?,?,?,?)",
                (entry_id, user["id"], user["name"], issue),
            )
            row = db.execute("SELECT * FROM entries WHERE id=?", (entry_id,)).fetchone()
            return ticket(row, db)
        if path == "/serve":
            row = db.execute(
                "SELECT entries.*, users.email FROM entries JOIN users ON users.id=entries.user_id WHERE entries.status='waiting' ORDER BY entries.seq LIMIT 1"
            ).fetchone()
            if not row:
                raise AppError("There is nobody waiting.", 409)
            db.execute("UPDATE entries SET status='served' WHERE id=?", (row["id"],))
            client_email = row["email"]
            client_id = row["id"]
            client_name = row["name"]
            client_issue = row["issue"]
        else:
            entry_id = data.get("id")
            if not isinstance(entry_id, str):
                raise AppError("Provide a client ID.")
            row = db.execute(
                "SELECT * FROM entries WHERE id=? AND user_id=?", (entry_id, user["id"])
            ).fetchone()
            if not row:
                raise AppError("Client not found.", 404)
            if path == "/acknowledge":
                db.execute("UPDATE entries SET notified=1 WHERE id=?", (entry_id,))
                return {"message": "Notification acknowledged"}
            if row["status"] != "waiting":
                raise AppError("You are no longer waiting.", 409)
            db.execute("UPDATE entries SET status='left' WHERE id=?", (entry_id,))
            return {"name": row["name"], "message": "You have left the queue"}

    # Send email notification after database transaction completes
    try:
        send_email(client_email, "served")
    except Exception:
        pass
    return {
        "id": client_id,
        "name": client_name,
        "issue": client_issue,
        "message": "Client called",
    }


def set_admin(email, pin="123456"):
    email = email_address(email)
    validate_pin_format(str(pin))
    hashed_pin = pin_hash(str(pin))
    with connect() as db:
        row = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
        if not row or not row["verified"]:
            raise AppError("Register and verify this account first.")
        db.execute("UPDATE users SET role='admin', admin_pin=? WHERE id=?", (hashed_pin, row["id"]))
        db.execute(
            "UPDATE entries SET status='left', notified=1 WHERE user_id=? AND status='waiting'",
            (row["id"],),
        )
        db.execute(
            "UPDATE entries SET notified=1 WHERE user_id=? AND status='served'",
            (row["id"],),
        )
        db.execute("DELETE FROM sessions WHERE user_id=?", (row["id"],))
