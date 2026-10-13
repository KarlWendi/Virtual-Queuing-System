# Accounts and email setup

Accounts, sessions, verification links, and queue entries are stored in `data/queue.sqlite3`. Keep this directory private and back it up; it is excluded from Git. The database is created automatically. Passwords are stored as salted scrypt hashes. Sessions expire after 12 hours; logout revokes the session. Reset links expire after 30 minutes and verification links after 24 hours; both are single-use.

## Local testing without sending email

In PowerShell:

```powershell
$env:QUEUE_EMAIL_MODE = "file"
python server.py
```

Register through the browser. The verification email is saved as a JSON file under `data/dev-mail/`. Open it locally and follow its link. These files contain private one-time links: never upload or share them. This mode is only for local development. It does not send real emails or bypass verification.

## Real email delivery

Set these environment variables in the terminal or hosting provider's secret settings:

- `QUEUE_BASE_URL`: the site's trusted URL, for example `https://queue.example.com`; used in email links and secure cookies.
- `SMTP_HOST`, `SMTP_PORT` (587 for STARTTLS or 465 for TLS).
- `SMTP_USERNAME`, `SMTP_PASSWORD`: your provider's credentials.
- `SMTP_FROM`: your verified sending address.

Remove `QUEUE_EMAIL_MODE` for SMTP delivery. Do not put credentials in source files or Git. Missing email configuration blocks registration and email requests with a clear error. Failed sends can be retried with Resend verification.

For Resend, configure a sender domain and use the SMTP settings from its dashboard/documentation. Provider credentials and domain DNS records require account-owner setup.

## Assign admin access

First register and verify the intended administrator. Stop the server, then run:

```powershell
python server.py --make-admin your-address@example.com
```

Restart the server and sign in again. Registration never grants admin rights, and being first to register does not make an account an administrator. Admin authorization is enforced on the server.

## Hosting

This is still a local prototype, not an online deployment. The default listener is localhost. Outside local testing, use HTTPS and set `QUEUE_BASE_URL` to the HTTPS address. HTTP-only remote account access is refused at startup. Configure a TLS reverse proxy or hosting service before enabling external access. Use `QUEUE_HOST` and `QUEUE_PORT` for hosting configuration.

The original Tkinter app is archived in the repository but is not compatible with the new signed-in API. Use the browser app.

Clients can only leave or inspect their own queue entry; only an admin can serve the next client. Clients see other people's names and positions but not their support issues. Signing out and closing a browser retain the queue entry; clients can recover it by signing in again.

## Gmail: initial real-email testing without a domain

1. Turn on Google 2-Step Verification: https://myaccount.google.com/security
2. Create an app password named **IT Help Desk Queue**: https://myaccount.google.com/apppasswords
3. Stop any server running on port 8000.
4. Run:

```powershell
python start_gmail.py
```

Enter your personal Gmail address and the app password when prompted. The password input is hidden; it is held in memory and never written to the project or passed on the command line. Do not paste it into a chat or GitHub. The launcher sends one setup test message to your own Gmail inbox, then opens the Client and Admin pages and starts the server with real SMTP delivery. Check spam if the test message is missing; SMTP acceptance does not guarantee inbox placement.

Register with your Gmail address in the queue app and follow the verification link in your inbox. If you already registered during file-mode testing, choose **Resend verification** instead. Already verified accounts can test **Forgot password**. This launcher uses the same persistent database as the normal server.

If another server is using port 8000, stop it or use:

```powershell
python start_gmail.py --port 8004
```

Run this launcher whenever you want Gmail delivery; running `server.py` alone does not remember the password. Restarting invalidates previously issued email links only if you replace them with a new link; existing links must use the same port as when they were issued.

Google app passwords require 2-Step Verification and are unavailable for some managed or Advanced Protection accounts. If the option is absent, use an eligible personal Gmail account or another mail service; do not use your regular Google password. Google's instructions: https://support.google.com/mail/answer/185833

This is for initial email testing. Links use localhost and can be opened on the server computer only. Deploy with an HTTPS site URL before inviting people on other devices. A dedicated transactional provider is the planned route for the hosted app.

Administrator accounts are admin-only: assigning the admin role removes an existing waiting entry and prevents client joins. Signing in at the Client page redirects administrators to `/admin`. The verified login account is retained.
