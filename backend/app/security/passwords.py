"""Argon2id password hashing and password policy."""
import re

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from argon2.low_level import Type

# OWASP-recommended Argon2id parameters (19 MiB+, t>=2). Tuned up slightly.
_hasher = PasswordHasher(time_cost=3, memory_cost=64 * 1024, parallelism=2, hash_len=32, salt_len=16, type=Type.ID)
# Used to keep login timing similar when the e-mail does not exist.
_DUMMY_HASH = _hasher.hash("timing-equalisation-only")

MIN_LENGTH = 10


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


def password_policy_errors(password: str, *, email: str = "") -> list[str]:
    errors = []
    if len(password) < MIN_LENGTH:
        errors.append(f"at least {MIN_LENGTH} characters")
    if len(password) > 128:
        errors.append("at most 128 characters")
    if not re.search(r"[a-z]", password):
        errors.append("a lower-case letter")
    if not re.search(r"[A-Z]", password):
        errors.append("an upper-case letter")
    if not re.search(r"\d", password):
        errors.append("a number")
    if not re.search(r"[^\w\s]", password):
        errors.append("a symbol")
    local = email.split("@")[0].lower()
    if local and len(local) >= 4 and local in password.lower():
        errors.append("must not contain your e-mail name")
    return errors
