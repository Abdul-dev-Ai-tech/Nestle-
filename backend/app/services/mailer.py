"""Minimal SMTP mailer for password-reset links. Disabled unless SMTP_HOST is configured.

Check your mail settings (reads backend/.env):
    python -m app.services.mailer --test you@company.com
"""
import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formatdate, make_msgid

from app.core.config import get_settings

log = logging.getLogger(__name__)


def _mask(addr: str) -> str:
    """j***@company.com — keeps logs useful without writing full e-mail addresses."""
    name, _, domain = addr.partition("@")
    return f"{name[:1]}***@{domain}" if domain else "***"


def _deliver(msg: EmailMessage) -> None:
    """Send one message; raises on any failure. Port 465 (or SMTP_SSL=true) uses implicit TLS, otherwise STARTTLS."""
    s = get_settings()
    ctx = ssl.create_default_context()
    use_ssl = s.SMTP_SSL if s.SMTP_SSL is not None else s.SMTP_PORT == 465
    if use_ssl:
        smtp: smtplib.SMTP = smtplib.SMTP_SSL(s.SMTP_HOST, s.SMTP_PORT, timeout=15, context=ctx)
    else:
        smtp = smtplib.SMTP(s.SMTP_HOST, s.SMTP_PORT, timeout=15)
    with smtp:
        smtp.ehlo()
        if not use_ssl and s.SMTP_STARTTLS:
            smtp.starttls(context=ctx)
            smtp.ehlo()
        if s.SMTP_USERNAME:
            smtp.login(s.SMTP_USERNAME, s.SMTP_PASSWORD)
        smtp.send_message(msg)


def _build(to: str, subject: str, body: str) -> EmailMessage:
    s = get_settings()
    sender = s.SMTP_FROM or s.SMTP_USERNAME
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = sender, to, subject
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid(domain=sender.partition("@")[2] or None)
    msg.set_content(body)
    return msg


def send_mail(to: str, subject: str, body: str) -> bool:
    s = get_settings()
    if not s.SMTP_HOST:
        log.warning("SMTP is not configured (SMTP_HOST is empty); e-mail to %s was NOT sent (subject: %s)", _mask(to), subject)
        return False
    try:
        _deliver(_build(to, subject, body))
        log.info("E-mail sent to %s (subject: %s)", _mask(to), subject)
        return True
    except smtplib.SMTPAuthenticationError as exc:
        log.error("SMTP login rejected by %s (code %s). Check SMTP_USERNAME / SMTP_PASSWORD - Gmail needs an App Password.",
                  s.SMTP_HOST, exc.smtp_code)
    except (smtplib.SMTPException, OSError) as exc:
        log.error("Could not send e-mail via %s:%s - %s: %s", s.SMTP_HOST, s.SMTP_PORT, type(exc).__name__, exc)
    return False


if __name__ == "__main__":  # pragma: no cover - manual check
    import argparse
    import sys

    p = argparse.ArgumentParser(description="Send a test e-mail with the SMTP settings from backend/.env")
    p.add_argument("--test", metavar="TO", required=True, help="recipient address")
    to = p.parse_args().test
    s = get_settings()
    if not s.SMTP_HOST:
        sys.exit("SMTP_HOST is empty in backend/.env - fill in the SMTP_* settings first.")
    print(f"Server {s.SMTP_HOST}:{s.SMTP_PORT}  user {s.SMTP_USERNAME or '(none)'}  from {s.SMTP_FROM or s.SMTP_USERNAME}")
    try:
        _deliver(_build(to, "Test e-mail - Nestle AI Compliance", "SMTP is configured correctly. Password-reset e-mails will work."))
    except smtplib.SMTPAuthenticationError as exc:
        sys.exit(f"FAILED: login rejected (code {exc.smtp_code}). For Gmail use a 16-character App Password, not your normal password.")
    except (smtplib.SMTPException, OSError) as exc:
        sys.exit(f"FAILED: {type(exc).__name__}: {exc}")
    print(f"OK - test e-mail sent to {to}. Check the inbox (and the spam folder).")
