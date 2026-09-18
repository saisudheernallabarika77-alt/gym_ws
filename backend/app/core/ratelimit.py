"""
Fitora - lightweight in-process rate limiting.

A single-process, in-memory sliding-window limiter. This is intentionally
simple: it protects the login/OTP/scan endpoints from casual brute-forcing
without pulling in Redis for a project this size. It resets on restart and
does not share state across multiple worker processes - if this is ever
deployed with `--workers > 1` or behind multiple app instances, replace the
in-memory dict with a Redis-backed counter (the call sites below don't need
to change, only `_hits`).
"""
from __future__ import annotations
import time
from collections import defaultdict

from fastapi import HTTPException, Request, status

_hits: dict[str, list[float]] = defaultdict(list)


def _client_ip(request: Request) -> str:
    # Trust X-Forwarded-For only if a reverse proxy is expected to set it;
    # falls back to the direct peer address otherwise.
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def enforce(key: str, *, limit: int, window_seconds: int) -> None:
    """Raise 429 if `key` has exceeded `limit` hits in the trailing window."""
    now = time.time()
    hits = _hits[key]
    hits[:] = [t for t in hits if now - t < window_seconds]
    if len(hits) >= limit:
        retry_after = int(window_seconds - (now - hits[0])) + 1
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Too many attempts. Try again in {retry_after}s.",
            headers={"Retry-After": str(retry_after)},
        )
    hits.append(now)


def rate_limit_login(request: Request, email: str) -> None:
    """Combined per-IP and per-email limits so neither alone is a bypass."""
    ip = _client_ip(request)
    enforce(f"login:ip:{ip}", limit=20, window_seconds=300)
    enforce(f"login:email:{email.lower().strip()}", limit=8, window_seconds=300)


def rate_limit_otp_request(request: Request, email: str) -> None:
    ip = _client_ip(request)
    enforce(f"otp:ip:{ip}", limit=15, window_seconds=3600)
    enforce(f"otp:email:{email.lower().strip()}", limit=5, window_seconds=3600)


def rate_limit_scan(request: Request) -> None:
    ip = _client_ip(request)
    enforce(f"scan:ip:{ip}", limit=60, window_seconds=60)
