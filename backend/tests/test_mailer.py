"""Mailer: configuration handling, TLS mode selection, failure handling and the forgot-password hand-off."""
import smtplib

import pytest

from app.core.config import get_settings
from app.services import mailer
from tests.conftest import AJAX


class FakeSMTP:
    instances: list["FakeSMTP"] = []
    fail_login = False

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port, self.ssl = host, port, context is not None
        self.started_tls = False
        self.logged_in = None
        self.sent = []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def ehlo(self):
        pass

    def starttls(self, context=None):
        self.started_tls = True

    def login(self, user, password):
        if FakeSMTP.fail_login:
            raise smtplib.SMTPAuthenticationError(535, b"bad credentials")
        self.logged_in = user

    def send_message(self, msg):
        self.sent.append(msg)


@pytest.fixture
def smtp(monkeypatch):
    FakeSMTP.instances, FakeSMTP.fail_login = [], False
    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)
    monkeypatch.setattr(mailer.smtplib, "SMTP_SSL", lambda h, p, timeout=None, context=None: FakeSMTP(h, p, timeout, context or True))
    s = get_settings()
    for k, v in {"SMTP_HOST": "smtp.example.com", "SMTP_PORT": 587, "SMTP_USERNAME": "sender@example.com",
                 "SMTP_PASSWORD": "app-password", "SMTP_FROM": "", "SMTP_SSL": None}.items():
        monkeypatch.setattr(s, k, v)
    return s


def test_not_configured_sends_nothing(monkeypatch):
    monkeypatch.setattr(get_settings(), "SMTP_HOST", "")
    assert mailer.send_mail("a@example.com", "x", "y") is False


def test_starttls_on_587(smtp):
    assert mailer.send_mail("to@example.com", "Subject", "Body") is True
    c = FakeSMTP.instances[-1]
    assert (c.port, c.ssl, c.started_tls, c.logged_in) == (587, False, True, "sender@example.com")
    msg = c.sent[0]
    assert msg["To"] == "to@example.com" and msg["From"] == "sender@example.com" and msg["Message-ID"]


def test_implicit_ssl_on_465(smtp, monkeypatch):
    monkeypatch.setattr(smtp, "SMTP_PORT", 465)
    assert mailer.send_mail("to@example.com", "Subject", "Body") is True
    c = FakeSMTP.instances[-1]
    assert c.ssl is True and c.started_tls is False


def test_login_failure_returns_false_without_leaking_password(smtp, caplog):
    FakeSMTP.fail_login = True
    assert mailer.send_mail("to@example.com", "Subject", "Body") is False
    assert "app-password" not in caplog.text and "to@example.com" not in caplog.text


def test_forgot_password_emails_existing_user_only(smtp, anon):
    r = anon.post("/api/v1/auth/forgot-password", json={"email": "viewer@example.com"}, headers=AJAX)
    assert r.status_code == 200
    mail = FakeSMTP.instances[-1].sent[0]
    assert mail["To"] == "viewer@example.com" and "/reset-password?token=" in mail.get_content()
    count = len(FakeSMTP.instances)
    r = anon.post("/api/v1/auth/forgot-password", json={"email": "nobody@example.com"}, headers=AJAX)
    assert r.status_code == 200 and len(FakeSMTP.instances) == count  # same answer, no e-mail
