"""Encryption of camera credentials at rest (Fernet / AES-128-CBC + HMAC)."""
import json

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


class CredentialKeyMissing(RuntimeError):
    pass


def _fernet() -> Fernet:
    key = get_settings().CAMERA_CREDENTIALS_KEY
    if not key:
        raise CredentialKeyMissing("CAMERA_CREDENTIALS_KEY is not configured")
    return Fernet(key.encode())


def encrypt_credentials(username: str, password: str) -> str:
    return _fernet().encrypt(json.dumps({"u": username, "p": password}).encode()).decode()


def decrypt_credentials(token: str | None) -> tuple[str, str] | None:
    if not token:
        return None
    try:
        data = json.loads(_fernet().decrypt(token.encode()))
        return data.get("u", ""), data.get("p", "")
    except (InvalidToken, ValueError):
        return None
