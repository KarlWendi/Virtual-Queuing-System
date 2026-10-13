# Free prototype hosting with PythonAnywhere

The live Client app is https://karl213.pythonanywhere.com/ and the Admin page is https://karl213.pythonanywhere.com/admin. The steps below document how to reproduce this deployment.

Use a free account. Do not apply the paid Render blueprint. PythonAnywhere provides one web app and 512 MiB file storage; the web app has a one-month expiry, so use its dashboard to renew before expiry. The support guidance describes Gmail SMTP access for free accounts, but verify it from your actual host before inviting users.

## Account and source

1. Register a free account at https://www.pythonanywhere.com/registration/register/beginner/ (or its EU service).
2. In a Bash console, clone:

```sh
git clone https://github.com/KarlWendi/Virtual-Queuing-System.git
cd Virtual-Queuing-System
```

3. In **Web → Add a new web app**, choose the free PythonAnywhere subdomain, **Manual configuration**, and a supported Python 3 version (3.10 or newer).
4. Open the WSGI configuration file shown on the Web tab and replace its contents with the following, substituting your actual account username:

```python
import sys

project_path = "/home/YOUR_USERNAME/Virtual-Queuing-System"
if project_path not in sys.path:
    sys.path.insert(0, project_path)

from wsgi_app import application
```

No additional Python packages are required. Do not start `server.py` in a console; the host runs `application` through WSGI.

## Email and HTTPS

In the project's Bash console run:

```sh
python configure_pythonanywhere.py
```

Enter the HTTPS URL shown on the Web tab, your Gmail sending address, and the Google app password at the hidden prompt. The helper checks Gmail authentication before saving. It does not send a test email or upload secrets to Git. Private settings are saved in `data/hosting.json` with owner-only permissions. Never make `data/` a static-files directory.

Enable **Force HTTPS** on the Web tab and reload the web app. Open your site's HTTPS URL and register. Verify that email delivery works and the verification link contains your hosted URL. The SQLite database is held in the account's private disk storage and must be backed up. The hosted database starts empty; local accounts are not uploaded.

## Administrator

After registering and verifying the administrator, run in the Bash console:

```sh
cd ~/Virtual-Queuing-System
python server.py --make-admin your-address@example.com
```

Then sign in again through the hosted `/admin` page. Keep SMTP settings private. This command only grants the role and does not start a server.

## Final checks before sharing

- Open the site from a different device, register, verify, and sign in.
- Test password-reset email delivery.
- Join from two different accounts and verify first-come order.
- Serve from the verified admin account and check client notifications.
- Confirm a normal client cannot serve or remove another client's place.
- Reload the hosted web app and verify that accounts and queue entries remain.
- Note the free-app expiry date and renew it before expiry.

If Gmail authentication fails from the host, the helper stops without saving credentials. Do not promise email delivery until the hosted check passes. Consult PythonAnywhere support or use an allowed HTTPS email provider.
