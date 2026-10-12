# Virtual Queuing System

A browser-based IT help desk queue with a Python server. Clients join in order, see their position and people ahead, leave the queue, and receive an in-page notification when called. Admins use a separate page to serve the next person.

## Run the browser app

Requires Python 3. No third-party packages are needed.

```sh
python server.py
```

Leave the server running and open:

- Client: http://127.0.0.1:8000/
- Admin: http://127.0.0.1:8000/admin

The queue refreshes every two seconds. Use separate browser profiles or private windows for different accounts. A client's place is tied to their account and survives refreshes and server restarts.

The account-enabled server defaults to localhost. Remote sign-in requires HTTPS hosting; online hosting is not configured yet.

## Browser behaviour

Click **Leave Queue** to leave. Closing a browser tab keeps the entry in the queue: browsers cannot reliably notify the server when a tab closes. Notifications appear while the client page is open; mobile browsers may delay updates when a page is in the background.

Accounts now require email verification. Admin actions require an assigned admin role. Accounts and queue data persist in SQLite. See [ACCOUNT_SETUP.md](ACCOUNT_SETUP.md) for email setup and local testing.

## Files

| File | Purpose |
| --- | --- |
| `server.py` | Browser pages and shared queue HTTP API |
| `web/index.html` | Client and Admin page structure |
| `web/style.css` | Responsive layout and styling |
| `web/app.js` | Joining, leaving, live refresh, and turn notifications |
| `First Window.py` | Previous Tkinter interface, still available |
| `queue_api.py` | HTTP helper used by the Tkinter interface |

## API

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/queue` | Read the queue |
| GET | `/status/<client-id>` | Read waiting, served, or left status |
| POST | `/join` | Join with `name` and `issue` |
| POST | `/leave` | Leave with a client `id` |
| POST | `/serve` | Serve the first client; send `{}` |

## Manual test

1. Open the client page in two tabs and join as Adam and Sarah.
2. Open `/admin` and click **Serve Next**.
3. Adam receives a turn dialog, and Sarah becomes position 1.
4. Sarah clicks **Leave Queue** and the queue becomes empty.
5. Refresh a waiting client's tab and confirm their place is retained.
6. Test the layout on a narrow phone screen.

## Next stages

- Online hosting with a shared persistent queue.
- Configure a production email service and HTTPS hosting.
- Better recovery from interrupted requests.

## Verified accounts

Registration, sign-in, sign-out, verification resend, and password reset are available in the browser. Follow [ACCOUNT_SETUP.md](ACCOUNT_SETUP.md) before testing accounts. Real email delivery still needs provider configuration.

For real email testing with a Gmail account, run `python start_gmail.py` and follow the [Gmail setup instructions](ACCOUNT_SETUP.md#gmail-initial-real-email-testing-without-a-domain). You need a Google app password.

## Hosted deployment

A Python-compatible HTTPS deployment is prepared in `render.yaml`. It requires paid hosting and a persistent disk to keep Gmail SMTP and SQLite. See [DEPLOYMENT.md](DEPLOYMENT.md). No public deployment has been created yet.

## Free hosting option

PythonAnywhere deployment files are prepared; see [PYTHONANYWHERE.md](PYTHONANYWHERE.md). This is the selected free prototype route. The paid Render configuration is retained only as an optional alternative. No public deployment has been created yet.
