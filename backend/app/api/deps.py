"""Fitora - shared FastAPI dependencies (auth guards, DB session)."""
from __future__ import annotations
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..core.security import decode_access_token
from ..db.models import Admin, GymOwner, User, UserStatus
from ..db.session import get_db

bearer = HTTPBearer(auto_error=False)

DbSession = Annotated[Session, Depends(get_db)]
Creds = Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]


def _payload(creds: Creds) -> dict:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    data = decode_access_token(creds.credentials)
    if data is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    return data


def current_user(creds: Creds, db: DbSession) -> User:
    data = _payload(creds)
    if data.get("role") != "user":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "User account required")
    user = db.get(User, int(data["sub"]))
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found")
    if user.status is UserStatus.blocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            f"Account blocked. {user.blocked_reason or ''}".strip())
    if user.status is UserStatus.deleted:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account no longer exists")
    return user


def current_owner(creds: Creds, db: DbSession) -> GymOwner:
    data = _payload(creds)
    if data.get("role") != "gym_owner":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Gym partner account required")
    owner = db.get(GymOwner, int(data["sub"]))
    if not owner:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found")
    if owner.status is UserStatus.blocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Partner account suspended")
    return owner


def current_admin(creds: Creds, db: DbSession) -> Admin:
    data = _payload(creds)
    if data.get("role") not in ("admin", "superadmin"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin access required")
    admin = db.get(Admin, int(data["sub"]))
    if not admin or not admin.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Admin account not found")
    return admin


def optional_user(creds: Creds, db: DbSession) -> User | None:
    """For endpoints that personalise when logged in but work anonymously."""
    if creds is None:
        return None
    data = decode_access_token(creds.credentials)
    if not data or data.get("role") != "user":
        return None
    return db.get(User, int(data["sub"]))


def any_authenticated_principal(creds: Creds, db: DbSession) -> tuple[str, int]:
    """
    For endpoints shared across portals (e.g. the image uploader, used by
    both users setting a profile photo and gym owners adding equipment/coach
    photos) where the caller only needs to prove *some* valid login, not a
    specific role. Returns (role, id) rather than a full row, since the two
    principal types share no common shape.
    """
    data = _payload(creds)
    role, sub = data.get("role"), data.get("sub")
    table = {"user": User, "gym_owner": GymOwner, "admin": Admin, "superadmin": Admin}
    model = table.get(role)
    if model is None or not sub:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token")
    row = db.get(model, int(sub))
    if not row:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Account not found")
    if role == "user" and row.status is UserStatus.blocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account blocked")
    return role, int(sub)


CurrentUser = Annotated[User, Depends(current_user)]
CurrentOwner = Annotated[GymOwner, Depends(current_owner)]
CurrentAdmin = Annotated[Admin, Depends(current_admin)]
OptionalUser = Annotated[User | None, Depends(optional_user)]
AnyPrincipal = Annotated[tuple[str, int], Depends(any_authenticated_principal)]
