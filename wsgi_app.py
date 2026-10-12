"""WSGI entry point for PythonAnywhere, reusing the existing request handlers."""

import io
import json
import os
from email.message import Message
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SETTINGS = ROOT / "data" / "hosting.json"
if SETTINGS.exists():
    config = json.loads(SETTINGS.read_text(encoding="utf-8"))
    for key in (
        "QUEUE_BASE_URL",
        "SMTP_HOST",
        "SMTP_PORT",
        "SMTP_USERNAME",
        "SMTP_PASSWORD",
        "SMTP_FROM",
    ):
        if key in config:
            os.environ[key] = str(config[key])
    os.environ.pop("QUEUE_EMAIL_MODE", None)

import accounts
from server import QueueRequestHandler

accounts.initialize()


def application(environ, start_response):
    method = environ.get("REQUEST_METHOD", "GET")
    if method not in ("GET", "POST"):
        payload = b'{"error":"Method not allowed"}'
        start_response(
            "405 Method Not Allowed",
            [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(payload))),
                ("Allow", "GET, POST"),
            ],
        )
        return [payload]

    handler = QueueRequestHandler.__new__(QueueRequestHandler)
    handler.command = method
    handler.request_version = "HTTP/1.1"
    handler.requestline = method + " " + environ.get("PATH_INFO", "/") + " HTTP/1.1"
    handler.path = environ.get("PATH_INFO", "/")
    if environ.get("QUERY_STRING"):
        handler.path += "?" + environ["QUERY_STRING"]
    handler.client_address = (environ.get("REMOTE_ADDR", "unknown"), 0)
    handler.close_connection = True
    handler.headers = Message()
    for key, value in environ.items():
        if key.startswith("HTTP_"):
            handler.headers[key[5:].replace("_", "-")] = str(value)
    for key in ("CONTENT_TYPE", "CONTENT_LENGTH"):
        if key in environ:
            handler.headers[key.replace("_", "-")] = str(environ[key])

    try:
        length = int(environ.get("CONTENT_LENGTH") or "0")
    except ValueError:
        length = 0
    body = environ["wsgi.input"].read(length) if 0 < length <= 8192 else b""
    handler.rfile = io.BytesIO(body)
    handler.wfile = io.BytesIO()
    if method == "GET":
        handler.do_GET()
    else:
        handler.do_POST()

    header_block, payload = handler.wfile.getvalue().split(b"\r\n\r\n", 1)
    lines = header_block.decode("latin-1").split("\r\n")
    status = lines[0].split(" ", 1)[1]
    headers = []
    for line in lines[1:]:
        key, value = line.split(":", 1)
        if key.lower() not in ("connection", "transfer-encoding", "keep-alive"):
            headers.append((key, value.strip()))
    start_response(status, headers)
    return [payload]
