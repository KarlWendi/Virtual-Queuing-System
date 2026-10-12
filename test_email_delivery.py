"""SMTP checks mock the mail provider: these tests do not send real email."""

import os
import smtplib
import unittest
from unittest.mock import patch, MagicMock
import accounts
import start_gmail


class EmailDeliveryTest(unittest.TestCase):
    def settings(self):
        return {
            "SMTP_HOST": "smtp.gmail.com",
            "SMTP_PORT": "465",
            "SMTP_USERNAME": "sender@gmail.com",
            "SMTP_PASSWORD": "test-secret",
            "SMTP_FROM": "sender@gmail.com",
        }

    def test_verification_and_reset_use_tls(self):
        with patch.dict(os.environ, self.settings(), clear=True), patch(
            "accounts.smtplib.SMTP_SSL"
        ) as factory:
            connection = factory.return_value
            for kind in ("verify", "reset"):
                accounts.send_email(
                    "recipient@example.test", kind, "one-time-test-token"
                )
                connection.login.assert_called_with("sender@gmail.com", "test-secret")
                mail = connection.send_message.call_args.args[0]
                self.assertEqual(mail["To"], "recipient@example.test")
                self.assertEqual(mail["From"], "sender@gmail.com")
                expected_path = "/verify" if kind == "verify" else "/reset"
                self.assertIn(
                    expected_path + "#token=one-time-test-token", mail.get_content()
                )
            self.assertEqual(factory.call_args.args[:2], ("smtp.gmail.com", 465))
            self.assertIsNotNone(factory.call_args.kwargs["context"])

    def test_starttls_is_used_for_port_587(self):
        settings = self.settings()
        settings["SMTP_PORT"] = "587"
        with patch.dict(os.environ, settings, clear=True), patch(
            "accounts.smtplib.SMTP"
        ) as factory:
            accounts.send_email("recipient@example.test", "verify", "test-token")
            factory.return_value.starttls.assert_called_once()
            factory.return_value.send_message.assert_called_once()

    def test_authentication_failure_is_readable(self):
        with patch.dict(os.environ, self.settings(), clear=True), patch(
            "accounts.smtplib.SMTP_SSL"
        ) as factory:
            factory.return_value.login.side_effect = smtplib.SMTPAuthenticationError(
                535, b"rejected"
            )
            with self.assertRaises(accounts.AppError) as error:
                accounts.send_email("recipient@example.test", "verify", "test-token")
            self.assertEqual(error.exception.status, 503)
            self.assertNotIn("test-secret", str(error.exception))

    def test_launcher_disables_file_mode_without_saving_password(self):
        previous = {"QUEUE_EMAIL_MODE": "file"}
        with patch.dict(os.environ, previous, clear=True), patch(
            "sys.argv", ["start_gmail.py"]
        ), patch("builtins.input", return_value="sender@gmail.com"), patch(
            "start_gmail.getpass.getpass", return_value="abcdefghijklmnop"
        ), patch(
            "start_gmail.socket.socket"
        ) as socket_factory, patch(
            "start_gmail.smtplib.SMTP_SSL"
        ) as smtp_factory, patch(
            "start_gmail.runpy.run_path"
        ) as run, patch(
            "builtins.print"
        ):
            smtp_factory.return_value.__enter__.return_value.send_message.return_value = (
                {}
            )

            def started(*args, **kwargs):
                self.assertNotIn("QUEUE_EMAIL_MODE", os.environ)
                self.assertEqual(os.environ["SMTP_HOST"], "smtp.gmail.com")
                self.assertEqual(os.environ["SMTP_PASSWORD"], "abcdefghijklmnop")
                self.assertEqual(os.environ["QUEUE_BASE_URL"], "http://127.0.0.1:8000")

            run.side_effect = started
            start_gmail.main()
            run.assert_called_once()
            mail = smtp_factory.return_value.__enter__.return_value.send_message.call_args.args[
                0
            ]
            self.assertEqual(mail["From"], mail["To"])
            self.assertEqual(os.environ["QUEUE_EMAIL_MODE"], "file")
            self.assertNotIn("SMTP_PASSWORD", os.environ)


if __name__ == "__main__":
    unittest.main()
