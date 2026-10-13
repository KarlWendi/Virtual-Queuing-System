# Virtual Queuing System

A browser-based IT help desk queue with verified email accounts, first-come ordering, live positions, and a separate administrator screen.

## Live app

- **Client:** https://karl213.pythonanywhere.com/
- **Admin:** https://karl213.pythonanywhere.com/admin

The app is deployed on PythonAnywhere's free plan with Gmail email delivery and persistent SQLite storage. Its free web app must be renewed monthly through the hosting dashboard.

## Features

- Anyone can create an account with an email address and password.
- Email verification is required before signing in.
- Verification resend, sign-out, and password reset are available.
- Clients join with their account name and an IT support issue.
- The queue shows numbered places and people ahead, updating every two seconds.
- Each client can have only one waiting entry and can leave only their own entry.
- Administrators can view support issues and serve the first waiting client.
- Called clients receive an in-page turn notification.
- Admin accounts are admin-only: they cannot join the client queue and are redirected to the Admin page.
- Accounts and queue records survive page refreshes and server restarts.

## Using the app

1. Open the Client link and choose **Create account**.
2. Follow the verification link in your email, then sign in.
3. Select an IT support issue and choose **Join Queue**.
4. Keep the page open for updates and your turn notification.
5. Choose **Leave Queue** to leave.

Use separate browser profiles or private windows for different test accounts. Tabs in the same browser profile share a sign-in. Closing a tab or signing out keeps a waiting place; signing back in recovers it.

Managers register and verify their email too. Only the hosting-account owner can assign admin access; registration cannot grant it. See [ACCOUNT_SETUP.md](ACCOUNT_SETUP.md).

## Run locally

Requires Python 3.10 or newer with no third-party runtime packages.

```sh
git clone https://github.com/KarlWendi/Virtual-Queuing-System.git
cd Virtual-Queuing-System
python server.py
```

The server opens Client and Admin tabs automatically. Leave it running. Local pages are at `http://127.0.0.1:8000/` and `/admin`.

Accounts need email configuration. For local development without sending email, set `QUEUE_EMAIL_MODE=file` before starting; private verification messages are saved under `data/dev-mail/`. For real Gmail delivery, run `python start_gmail.py` and enter a Google app password at its hidden prompt. Full instructions are in [ACCOUNT_SETUP.md](ACCOUNT_SETUP.md).

The previous Tkinter files are retained as an archived development stage. They are not compatible with the current authenticated API and are not needed for the browser app.

## Project files

| File | Purpose |
| --- | --- |
| `server.py` | Local HTTP server, browser assets, and authenticated API |
| `accounts.py` | Account security, email links, sessions, and persistent queue |
| `web/` | Responsive browser interface |
| `wsgi_app.py` | PythonAnywhere web-server entry point |
| `configure_pythonanywhere.py` | Private hosted Gmail configuration |
| `start_gmail.py` | Local Gmail launcher with hidden credential input |
| `test_accounts.py` | Account, permission, persistence, and queue checks |
| `test_email_delivery.py` | Simulated SMTP and credential-handling checks |
| `test_wsgi.py` | Hosting adapter checks |
| `browser_checks.py` | Optional real-browser checks using Playwright and installed Edge |

## Tests

Run the standard-library integration checks:

```sh
python -m unittest discover -v
```

Tests use temporary databases and simulated email delivery, leaving real accounts and queue data untouched. `browser_checks.py` additionally needs Playwright and the installed Microsoft Edge browser; it also uses isolated test data.

## Hosting

Follow [PYTHONANYWHERE.md](PYTHONANYWHERE.md) for the selected free hosting setup, Gmail verification, administrator assignment, and monthly renewal. HTTPS is enabled on the live site. Hosted account and email configuration is stored privately in the hosting account.

The optional paid Render configuration remains in `render.yaml`; it is not the active hosting service. See [DEPLOYMENT.md](DEPLOYMENT.md) only if you choose that alternative.

## API overview

| Method | Endpoint | Purpose |
| --- | --- | --- |
| GET | `/health` | Health check |
| GET | `/auth/me` | Current sign-in and CSRF token |
| POST | `/auth/register`, `/auth/verify` | Create and verify an account |
| POST | `/auth/login`, `/auth/logout` | Sign in and out |
| POST | `/auth/resend`, `/auth/forgot`, `/auth/reset` | Verification resend and password recovery |
| GET | `/queue`, `/my-ticket`, `/status/<client-id>` | Authorized queue and owned ticket details |
| POST | `/join`, `/leave` | Client queue actions |
| POST | `/serve` | Admin-only serving |
| POST | `/acknowledge` | Acknowledge a turn notification |

Queue writes require an authenticated verified account and a CSRF token. The server controls account roles, queue ownership, and support-issue visibility.

## Current limits

The free host is intended for a small prototype and has resource and renewal limits. Notifications require an open page and may be delayed in background mobile tabs. Passwords, mail credentials, user databases, and generated test artifacts are excluded from GitHub. Back up the private hosted database separately.
