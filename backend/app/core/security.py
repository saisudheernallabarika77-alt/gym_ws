"""Fitora - password hashing, JWT tokens, OTP generation, QR payload signing."""
from __future__ import annotations
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from passlib.context import CryptContext

from .config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=12)


# ------------------------------------------------------------------ passwords
def hash_password(raw: str) -> str:
    return pwd_context.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return pwd_context.verify(raw, hashed)
    except Exception:
        return False


# ---------------------------------------------------------------------- JWT
def create_access_token(
    subject: str | int,
    role: str,
    extra: dict[str, Any] | None = None,
    minutes: int | None = None,
) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "role": role,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=minutes or settings.ACCESS_TOKEN_MINUTES)).timestamp()),
        "iss": "fitora",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        return jwt.decode(
            token, settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM], issuer="fitora",
        )
    except jwt.PyJWTError:
        return None


# ---------------------------------------------------------------------- OTP
def generate_otp(length: int | None = None) -> str:
    n = length or settings.OTP_LENGTH
    return "".join(secrets.choice("0123456789") for _ in range(n))


def hash_otp(code: str) -> str:
    """OTPs are short, so bcrypt is overkill; an HMAC with the app secret is enough."""
    return hmac.new(settings.JWT_SECRET.encode(), code.encode(), hashlib.sha256).hexdigest()


def verify_otp(code: str, code_hash: str) -> bool:
    return hmac.compare_digest(hash_otp(code), code_hash)


# ------------------------------------------------------------- entry-pass QR
def sign_pass_payload(data: dict[str, Any]) -> str:
    """
    Build the QR payload for a gym entry pass.

    Format:  <base64url(json)>.<hmac-sha256 signature>
    The gym's scanner app verifies the signature offline, so a screenshot of
    someone else's pass cannot be forged into a valid one.
    """
    import base64
    body = json.dumps(data, separators=(",", ":"), sort_keys=True).encode()
    b64 = base64.urlsafe_b64encode(body).decode().rstrip("=")
    sig = hmac.new(settings.PASS_QR_SECRET.encode(), b64.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{b64}.{sig}"


def verify_pass_payload(payload: str) -> dict[str, Any] | None:
    import base64
    try:
        b64, sig = payload.rsplit(".", 1)
    except ValueError:
        return None
    expected = hmac.new(settings.PASS_QR_SECRET.encode(), b64.encode(), hashlib.sha256).hexdigest()[:32]
    if not hmac.compare_digest(sig, expected):
        return None
    try:
        pad = "=" * (-len(b64) % 4)
        return json.loads(base64.urlsafe_b64decode(b64 + pad))
    except Exception:
        return None


# ------------------------------------------------------------------- codes
def generate_code(prefix: str, length: int = 10) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"   # no ambiguous chars
    return prefix + "".join(secrets.choice(alphabet) for _ in range(length))
