"""Fitora - FastAPI application entrypoint."""
from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from .api import admin, auth, chat, gyms, membership, owner, profile
from .core.config import settings
from .db.session import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
# These libraries log every HTTP call and segment load at DEBUG/INFO, which
# buries our own startup and request lines.
for _noisy in ("chromadb", "urllib3", "httpx", "httpcore",
               "sentence_transformers", "filelock", "asyncio"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

log = logging.getLogger("fitora")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    log.info("Fitora API starting  env=%s  db=%s",
             settings.ENV, settings.DATABASE_URL.split("/")[-1])
    try:
        from .rag.vector_store import GymVectorStore
        n = GymVectorStore.get().count()
        log.info("RAG index: %d gyms%s", n,
                 "" if n else "  (run: python -m scripts.build_index)")
    except Exception as e:
        log.warning("RAG index not ready: %s", e)

    yield
    log.info("Fitora API shutting down")


app = FastAPI(
    title="Fitora API",
    description=(
        "Gym discovery, booking, membership and digital entry pass platform "
        "for the Kakinada region. Three portals: user, gym owner, admin."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    # Dev convenience origins only apply outside production, so a production
    # deployment can never be reached via a stale localhost trust entry even
    # if FRONTEND_URL is misconfigured.
    allow_origins=(
        [settings.FRONTEND_URL]
        if settings.ENV == "production"
        else [settings.FRONTEND_URL, "http://localhost:3000", "http://127.0.0.1:3000"]
    ),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Created here rather than in lifespan: the mount is evaluated at import time.
_uploads = Path(settings.UPLOAD_DIR)
_uploads.mkdir(parents=True, exist_ok=True)
for _sub in ("members", "gyms", "equipment", "coaches", "gallery"):
    (_uploads / _sub).mkdir(exist_ok=True)

app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")

P = settings.API_PREFIX
app.include_router(auth.router, prefix=P)
app.include_router(gyms.router, prefix=P)
app.include_router(chat.router, prefix=P)
app.include_router(membership.router, prefix=P)
app.include_router(profile.router, prefix=P)
app.include_router(owner.router, prefix=P)
app.include_router(admin.router, prefix=P)


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    """Turn pydantic errors into one plain sentence the UI can show as-is."""
    first = exc.errors()[0] if exc.errors() else {}
    field = ".".join(str(p) for p in first.get("loc", [])[1:]) or "input"
    msg = first.get("msg", "Invalid input").replace("Value error, ", "")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"detail": f"{field}: {msg}", "errors": exc.errors()},
    )


@app.get("/")
def root():
    return {
        "name": "Fitora API",
        "version": "1.0.0",
        "region": "Kakinada, Andhra Pradesh (100 km radius)",
        "docs": "/docs",
        "portals": {
            "user": f"{P}/auth/login, {P}/gyms, {P}/chat",
            "gym_owner": f"{P}/auth/owner/login, {P}/owner/dashboard",
            "admin": f"{P}/auth/admin/login, {P}/admin/dashboard",
        },
    }


@app.get("/health")
def health():
    from .db.session import SessionLocal
    db_ok = True
    try:
        db = SessionLocal()
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db.close()
    except Exception:
        db_ok = False

    rag_count = 0
    try:
        from .rag.vector_store import GymVectorStore
        rag_count = GymVectorStore.get().count()
    except Exception:
        pass

    return {
        "status": "ok" if db_ok else "degraded",
        "database": "connected" if db_ok else "error",
        "rag_indexed_gyms": rag_count,
        "payment_gateway": settings.PAYMENT_GATEWAY,
        "smtp_enabled": settings.SMTP_ENABLED,
    }
