import os
import tempfile

from cryptography.fernet import Fernet

_tmp = tempfile.mkdtemp(prefix="nec-test-")
os.environ.update({
    "ENV": "test", "SECRET_KEY": "test-secret-key-0123456789-abcdefghijklmnopqrstuvwxyz",
    "DATABASE_URL": os.environ.get("TEST_DATABASE_URL") or f"sqlite:///{_tmp}/test.db", "STORAGE_DIR": f"{_tmp}/storage", "AI_MODE": "simulation",
    "DOOR_MODE": "simulation", "HARDWARE_DOORS_ENABLED": "false", "DEV_RETURN_RESET_LINK": "true",
    "CAMERA_CREDENTIALS_KEY": Fernet.generate_key().decode(), "LOGIN_MAX_ATTEMPTS": "5",
    "RATE_LIMIT_PER_MINUTE": "100000", "AUTH_RATE_LIMIT_PER_MINUTE": "100000", "COOKIE_SECURE": "false",
})

import io  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.ai.registry import set_detector  # noqa: E402
from app.ai.simulated import SimulatedDetector  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.seed import seed_demo, seed_reference  # noqa: E402
from app.db.session import SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.security.ratelimit import limiter  # noqa: E402

PASSWORD = "Test-Passw0rd!2026"
AJAX = {"X-Requested-With": "XMLHttpRequest"}


@pytest.fixture(scope="session", autouse=True)
def database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        seed_reference(db)
        seed_demo(db, samples=True, password=PASSWORD, quiet=True, days=5)
    yield


@pytest.fixture(autouse=True)
def _reset():
    limiter.reset()
    set_detector(SimulatedDetector(seed=1))
    yield


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


def make_client(email: str | None = None, password: str = PASSWORD) -> TestClient:
    c = TestClient(app)
    if email:
        r = c.post("/api/v1/auth/login", json={"email": email, "password": password}, headers=AJAX)
        assert r.status_code == 200, r.text
        c.headers.update({"X-CSRF-Token": c.cookies.get("nec_csrf")})
    return c


@pytest.fixture
def anon():
    return make_client()


@pytest.fixture
def admin():
    return make_client("super.admin@example.com")


@pytest.fixture
def factory_admin():
    return make_client("factory.admin@example.com")


@pytest.fixture
def manager():
    return make_client("security.manager@example.com")


@pytest.fixture
def operator():
    return make_client("security.operator@example.com")


@pytest.fixture
def viewer():
    return make_client("viewer@example.com")


def jpeg_bytes(size=(320, 240), color=(120, 140, 160)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, "JPEG")
    return buf.getvalue()
