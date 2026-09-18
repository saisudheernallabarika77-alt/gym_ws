"""Fitora - application settings (env-driven)."""
from __future__ import annotations
import secrets
from pathlib import Path
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]
PROJECT_DIR = BACKEND_DIR.parent

# Known-weak values that must never be used once ENV=production. Kept as a
# set so a leaked value (e.g. one that ends up in a public repo or chat log)
# can be added here and permanently blocked, not just changed once.
_BANNED_SECRETS = {
    "change-me-in-production-fitora-2026",
    "fitora-entry-pass-signing-key-2026",
    "",
}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(BACKEND_DIR / ".env"), env_file_encoding="utf-8", extra="ignore"
    )

    # ---- app ----
    APP_NAME: str = "Fitora"
    ENV: str = "development"
    DEBUG: bool = True
    API_PREFIX: str = "/api/v1"
    FRONTEND_URL: str = "http://localhost:3000"

    # ---- database ----
    # SQLite by default so the project runs with zero setup; point
    # DATABASE_URL at PostgreSQL for production.
    DATABASE_URL: str = f"sqlite:///{BACKEND_DIR / 'fitora.db'}"

    # ---- auth ----
    # No hardcoded default: an empty value here is caught by the ENV=production
    # guard below, and dev mode fills in a fresh random secret at startup
    # instead of falling back to a value that could ship in source control.
    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_MINUTES: int = 60 * 24 * 7
    PASS_QR_SECRET: str = ""

    # ---- OTP / SMTP ----
    OTP_LENGTH: int = 6
    OTP_TTL_MINUTES: int = 10
    OTP_MAX_ATTEMPTS: int = 5
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_NAME: str = "Fitora"
    SMTP_FROM_EMAIL: str = ""
    # when SMTP creds are blank the OTP is printed to the console instead
    SMTP_ENABLED: bool = False

    # ---- payments ----
    PAYMENT_GATEWAY: str = "mock"          # mock | razorpay
    PLATFORM_UPI_ID: str = "fitora@upi"
    PLATFORM_COMMISSION_PERCENT: float = 10.0
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    # Separate secret Razorpay signs webhook bodies with (set in the Razorpay
    # dashboard under Webhooks) - deliberately not the same value as
    # RAZORPAY_KEY_SECRET, so a leak of one doesn't compromise the other.
    RAZORPAY_WEBHOOK_SECRET: str = ""

    # ---- dues policy ----
    DEFAULT_GRACE_DAYS: int = 7
    WARNING_DAYS_BEFORE_DUE: int = 3

    # ---- RAG ----
    OLLAMA_HOST: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:1.5b"
    EMBED_MODEL: str = "all-MiniLM-L6-v2"
    CHROMA_DIR: str = str(BACKEND_DIR / "chroma_db")
    RAG_TOP_K: int = 6

    # ---- storage ----
    UPLOAD_DIR: str = str(BACKEND_DIR / "uploads")
    GYMS_JSON: str = str(PROJECT_DIR / "data" / "processed" / "gyms.json")

    # ---- geo ----
    REGION_CENTER_LAT: float = 16.9891
    REGION_CENTER_LON: float = 82.2475
    REGION_RADIUS_KM: float = 100.0


@lru_cache
def get_settings() -> Settings:
    s = Settings()

    if s.ENV == "production":
        missing = [
            name for name, val in (("JWT_SECRET", s.JWT_SECRET),
                                   ("PASS_QR_SECRET", s.PASS_QR_SECRET))
            if val in _BANNED_SECRETS or len(val) < 32
        ]
        if missing:
            raise RuntimeError(
                f"Refusing to start with ENV=production: {', '.join(missing)} "
                f"is missing, too short, or a known-weak placeholder. Set a "
                f"random 32+ character value (e.g. `python -c "
                f"\"import secrets; print(secrets.token_urlsafe(48))\"`) in "
                f"the environment before starting."
            )
    else:
        # Dev/test convenience: a fresh secret per process start means old
        # tokens and QR passes quietly stop verifying on restart instead of
        # the app running with a guessable, checked-into-history default.
        if s.JWT_SECRET in _BANNED_SECRETS:
            s.JWT_SECRET = secrets.token_urlsafe(48)
        if s.PASS_QR_SECRET in _BANNED_SECRETS:
            s.PASS_QR_SECRET = secrets.token_urlsafe(48)

    return s


settings = get_settings()
