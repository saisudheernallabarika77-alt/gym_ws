"""Fitora - user profile, reviews and file uploads."""
from __future__ import annotations
import shutil
import time
import uuid
from collections import defaultdict
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from ..core.config import settings
from ..db.models import (
    FitnessGoal, Gym, GymStatus, Membership, MembershipStatus, Review,
)
from ..schemas.auth import UserProfileUpdate
from .deps import AnyPrincipal, CurrentUser, DbSession

router = APIRouter(tags=["profile"])

ALLOWED_IMAGE = {".jpg", ".jpeg", ".png", ".webp"}
MAX_UPLOAD_MB = 5

# In-process daily upload quota per (role, id). Resets on restart and isn't
# shared across workers - fine for the single-process deployment this ships
# with; a multi-worker deployment should move this to Redis/the DB instead.
_UPLOAD_QUOTA_PER_DAY = 40
_upload_counts: dict[tuple[str, int], list[float]] = defaultdict(list)


def _check_upload_quota(principal: tuple[str, int]) -> None:
    now = time.time()
    window = _upload_counts[principal]
    window[:] = [t for t in window if now - t < 86400]
    if len(window) >= _UPLOAD_QUOTA_PER_DAY:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Upload limit reached ({_UPLOAD_QUOTA_PER_DAY}/day). Try again tomorrow.",
        )
    window.append(now)


class ReviewRequest(BaseModel):
    gym_code: str
    rating: int = Field(ge=1, le=5)
    title: str | None = Field(default=None, max_length=150)
    comment: str | None = Field(default=None, max_length=2000)


@router.put("/profile")
def update_profile(payload: UserProfileUpdate, db: DbSession, user: CurrentUser):
    data = payload.model_dump(exclude_unset=True, exclude_none=True)

    if "fitness_goal" in data:
        try:
            data["fitness_goal"] = FitnessGoal(data["fitness_goal"])
        except ValueError:
            data.pop("fitness_goal")

    if "phone" in data:
        digits = "".join(c for c in data["phone"] if c.isdigit())
        if len(digits) < 10:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "Enter a valid phone number")
        data["phone"] = "+91 " + digits[-10:]

    for k, v in data.items():
        setattr(user, k, v)
    db.commit()

    from .auth import _user_profile
    return {"success": True, "profile": _user_profile(user)}


@router.post("/profile/photo")
def upload_photo(db: DbSession, user: CurrentUser, file: UploadFile = File(...)):
    """The photo that appears on the entry pass."""
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_IMAGE:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"Use one of: {', '.join(sorted(ALLOWED_IMAGE))}")

    dest_dir = Path(settings.UPLOAD_DIR) / "members"
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = f"u{user.id}-{uuid.uuid4().hex[:10]}{ext}"
    dest = dest_dir / name

    size = 0
    with dest.open("wb") as out:
        while chunk := file.file.read(1 << 20):
            size += len(chunk)
            if size > MAX_UPLOAD_MB * 1024 * 1024:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                                    f"Image must be under {MAX_UPLOAD_MB} MB")
            out.write(chunk)

    user.photo_url = f"/uploads/members/{name}"
    db.commit()
    return {"success": True, "photo_url": user.photo_url}


@router.post("/uploads/image")
def upload_image(kind: str, principal: AnyPrincipal, file: UploadFile = File(...)):
    """
    Shared uploader for gym covers, gallery shots, equipment and coach photos.
    Requires *some* valid login (user, gym owner or admin) - not open to
    anonymous callers, and capped per-account per day to bound storage abuse.
    """
    _check_upload_quota(principal)
    kind = kind if kind in {"gyms", "equipment", "coaches", "gallery"} else "gyms"
    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_IMAGE:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"Use one of: {', '.join(sorted(ALLOWED_IMAGE))}")

    dest_dir = Path(settings.UPLOAD_DIR) / kind
    dest_dir.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex[:14]}{ext}"
    dest = dest_dir / name

    size = 0
    with dest.open("wb") as out:
        while chunk := file.file.read(1 << 20):
            size += len(chunk)
            if size > MAX_UPLOAD_MB * 1024 * 1024:
                out.close()
                dest.unlink(missing_ok=True)
                raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                                    f"Image must be under {MAX_UPLOAD_MB} MB")
            out.write(chunk)

    return {"success": True, "url": f"/uploads/{kind}/{name}"}


@router.post("/reviews", status_code=status.HTTP_201_CREATED)
def write_review(payload: ReviewRequest, db: DbSession, user: CurrentUser):
    gym = db.query(Gym).filter(Gym.gym_code == payload.gym_code.upper()).first()
    if not gym or gym.status is not GymStatus.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Gym not found")

    was_member = (db.query(Membership)
                  .filter(Membership.user_id == user.id,
                          Membership.gym_id == gym.id,
                          Membership.status != MembershipStatus.pending_payment)
                  .first())
    if not was_member:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "Only members of this gym can review it.")

    existing = (db.query(Review)
                .filter(Review.user_id == user.id, Review.gym_id == gym.id).first())
    if existing:
        existing.rating = payload.rating
        existing.title = payload.title
        existing.comment = payload.comment
        review = existing
        created = False
    else:
        review = Review(user_id=user.id, gym_id=gym.id, rating=payload.rating,
                        title=payload.title, comment=payload.comment)
        db.add(review)
        created = True
    db.flush()

    # recompute the gym's public rating from visible reviews
    rows = (db.query(Review)
            .filter(Review.gym_id == gym.id, Review.is_hidden.is_(False)).all())
    if rows:
        gym.rating = round(sum(r.rating for r in rows) / len(rows), 1)
        gym.review_count = len(rows)
    db.commit()

    return {"success": True, "review_id": review.id, "created": created,
            "gym_rating": gym.rating, "review_count": gym.review_count}
