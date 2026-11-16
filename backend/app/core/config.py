"""Application settings, loaded from environment variables / .env (never hard-coded)."""
from functools import lru_cache
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_PLACEHOLDERS = {"", "change-me", "changeme", "replace-with-a-long-random-string"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Nestlé AI Personnel Entry Compliance & Smart Access Control"
    ENV: Literal["development", "test", "staging", "production"] = "development"
    LOG_LEVEL: str = "INFO"

    # --- secrets / infrastructure (required, no defaults) ---
    SECRET_KEY: str
    DATABASE_URL: str

    # --- web / cookies ---
    CORS_ORIGINS: str = "http://localhost:5173"
    FRONTEND_URL: str = "http://localhost:5173"
    COOKIE_SECURE: bool = False
    COOKIE_SAMESITE: Literal["lax", "strict", "none"] = "lax"
    COOKIE_DOMAIN: str | None = None
    TRUST_PROXY_HEADERS: bool = False

    # --- sessions / login protection ---
    SESSION_IDLE_MINUTES: int = 30
    SESSION_ABSOLUTE_HOURS: int = 12
    LOGIN_MAX_ATTEMPTS: int = 5
    LOGIN_LOCK_MINUTES: int = 15
    RESET_TOKEN_TTL_MINUTES: int = 30
    DEV_RETURN_RESET_LINK: bool = False
    RATE_LIMIT_PER_MINUTE: int = 600
    AUTH_RATE_LIMIT_PER_MINUTE: int = 20

    # --- e-mail (optional; password-reset links) ---
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM: str = ""
    SMTP_STARTTLS: bool = True
    SMTP_SSL: bool | None = None  # None = automatic: implicit TLS on port 465, STARTTLS otherwise

    # --- storage ---
    STORAGE_DIR: str = "./storage"
    MAX_UPLOAD_MB: int = 5
    EVIDENCE_RETENTION_DAYS: int = 365

    # --- cameras ---
    CAMERA_CREDENTIALS_KEY: str = ""  # Fernet key; see docs/SECURITY.md
    CAMERA_OPEN_TIMEOUT_SECONDS: int = 8

    # --- AI ---
    AI_MODE: Literal["simulation", "yolo", "disabled"] = "simulation"
    YOLO_WEIGHTS: str = "./models/ppe.pt"
    AI_CLASS_MAP: str = "./app/ai/class_map.json"
    AI_DEFAULT_CONFIDENCE: float = 0.60
    AI_DEVICE: str = "cpu"

    # --- door hardware ---
    DOOR_MODE: Literal["simulation", "hardware"] = "simulation"
    HARDWARE_DOORS_ENABLED: bool = False

    # --- monitoring ---
    SENTRY_DSN: str = ""

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip().rstrip("/") for o in self.CORS_ORIGINS.split(",") if o.strip()]

    @property
    def is_production(self) -> bool:
        return self.ENV == "production"

    @model_validator(mode="after")
    def _validate_security(self) -> "Settings":
        if self.SECRET_KEY.strip().lower() in _PLACEHOLDERS or len(self.SECRET_KEY) < 32:
            raise ValueError("SECRET_KEY must be a random string of at least 32 characters")
        if self.ENV in ("staging", "production"):
            problems = []
            if not self.COOKIE_SECURE:
                problems.append("COOKIE_SECURE must be true (HTTPS only)")
            if self.DEV_RETURN_RESET_LINK:
                problems.append("DEV_RETURN_RESET_LINK must be false")
            if "*" in self.CORS_ORIGINS:
                problems.append("CORS_ORIGINS must be an explicit allow-list")
            if not self.CAMERA_CREDENTIALS_KEY:
                problems.append("CAMERA_CREDENTIALS_KEY must be set")
            if self.ENV == "production" and self.AI_MODE == "simulation":
                problems.append("AI_MODE=simulation is not allowed in production (use yolo or disabled)")
            if problems:
                raise ValueError("Unsafe configuration for %s: %s" % (self.ENV, "; ".join(problems)))
        if self.DOOR_MODE == "hardware" and not self.HARDWARE_DOORS_ENABLED:
            raise ValueError("DOOR_MODE=hardware requires HARDWARE_DOORS_ENABLED=true")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
