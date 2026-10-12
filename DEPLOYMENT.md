# HTTPS deployment with Render

The prepared `render.yaml` uses a $7/month Python web service and a 1 GB disk at $0.25/month: a base cost of approximately $7.25/month, before tax and any usage overages. Confirm current pricing in Render before deployment. This retains the current Gmail SMTP delivery and SQLite storage. Do not apply it until you approve the monthly compute and storage charges shown by Render. Free services block outbound SMTP and cannot use a persistent disk.

## Create the service

1. Sign in at https://dashboard.render.com/ using your account.
2. Choose **New → Blueprint** and connect `KarlWendi/Virtual-Queuing-System`.
3. Use the `main` branch and review the resources and charges before creating them.
4. Enter `SMTP_USERNAME` and `SMTP_FROM` as the sending Gmail address.
5. Enter `SMTP_PASSWORD` privately in Render's secret field as the Google app password. Never put it in Git or a chat. Local launcher credentials are not transferred automatically.
6. Deploy and wait for the health check to pass.
7. Open the HTTPS URL Render returns. Use exactly that URL for invitation links.

The app automatically uses Render's `RENDER_EXTERNAL_URL` in verification/reset links and sets Secure session cookies for HTTPS. Do not set `QUEUE_EMAIL_MODE=file` on the host. `PORT` is supplied by Render. The database is stored only on the persistent disk at `/var/data/queue.sqlite3`.

## Hosted account check

The hosted database starts empty; local accounts are not uploaded.

1. Register your own account at the hosted HTTPS URL.
2. Open the verification email on a different device and verify that the link uses the hosted URL, not `127.0.0.1`.
3. Sign in and join the queue.
4. Register and verify a second account using a separate browser profile.
5. Check joining/leaving and password reset email delivery.
6. Restart the service and confirm accounts and queue records remain.

## Assign the first administrator

After registering and verifying the account on the hosted app, use the service's Render Shell:

```sh
python server.py --make-admin your-address@example.com
```

Sign in again at `/admin`. This command uses the same disk database and does not start another server. Ordinary users cannot grant themselves admin access.

## Before sharing

- Run the hosted verification and password-reset checks above.
- Verify that `/health` returns `{"status":"ok"}`.
- Keep the persistent disk attached and keep the service at one instance because SQLite is local to that disk.
- Use Render's disk snapshot/backup options and protect access to the account.
- The original Tkinter app is archived and is not the hosted client.

If you need a zero-cost deployment, the current Gmail/SQLite approach needs to change: choose an email HTTPS API and a suitable persistent database first. A static-site deployment alone cannot run this application.
