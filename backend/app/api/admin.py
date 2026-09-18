"""
Fitora - Admin portal.

The admin controls the whole system:
  * users   - view, block, unblock, delete
  * gyms    - approve, suspend, edit, and ADD NEW GYMS MANUALLY (e.g. a gym in
              a village that has no owner account yet)
  * money   - all payments land here; the admin releases monthly payouts to
              each gym owner's bank account
  * dues    - the overdue list across every gym; only the admin can extend a
              grace period or remove a defaulting member
  * complaints raised by gym owners
"""
from __future__ import annotations
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import func

from ..core.security import generate_code, hash_password
from ..db.models import (
    Admin, AuditLog, Coach, Complaint, DietPlan, Equipment, EntryPass, Gym,
    GymOwner, GymPlan, GymStatus, Membership, MembershipStatus, Payment,
    PaymentStatus, Payout, PayoutStatus, Review, User, UserStatus,
)
from ..services.dues_service import (
    extend_grace, remove_member, run_daily_sweep, evaluate,
)
from ..services.payment_service import split_amount
from .deps import CurrentAdmin, DbSession

router = APIRouter(prefix="/admin", tags=["admin"])


# ------------------------------------------------------------------ schemas
class BlockRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class GracePeriodRequest(BaseModel):
    extra_days: int = Field(ge=1, le=90)
    reason: str = ""


class RemoveMemberRequest(BaseModel):
    reason: str = Field(min_length=3, max_length=500)


class AdminGymRequest(BaseModel):
    """Admin manually adding a gym (typically one with no owner account yet)."""
    name: str = Field(min_length=2, max_length=180)
    description: str | None = None
    gym_type: str = "Unisex"
    address_line: str
    locality: str
    district: str
    state: str = "Andhra Pradesh"
    pincode: str
    latitude: float
    longitude: float
    phone: str
    alt_phone: str | None = None
    email: str | None = None
    morning_open: str = "05:30"
    morning_close: str = "11:00"
    evening_open: str = "16:30"
    evening_close: str = "22:00"
    open_days: str = "Monday - Saturday"
    weekly_off: str | None = "Sunday"
    monthly_fee: int = Field(ge=0)
    registration_fee: int = Field(default=0, ge=0)
    coach_included: bool = False
    coach_fee_separate: int = Field(default=0, ge=0)
    trial_available: bool = False
    trial_days: int = Field(default=0, ge=0, le=30)
    is_air_conditioned: bool = False
    supplements_available: bool = False
    facilities: list[str] = Field(default_factory=list)
    established_year: int | None = None
    cover_image: str | None = None
    gallery: list[str] = Field(default_factory=list)
    # optionally create a partner login for this gym
    create_owner_account: bool = False
    owner_name: str | None = None
    owner_email: str | None = None
    owner_phone: str | None = None
    owner_password: str | None = None
    publish: bool = True


class PayoutRequest(BaseModel):
    gym_id: int
    period_month: int = Field(ge=1, le=12)
    period_year: int = Field(ge=2024, le=2100)


class PayoutReleaseRequest(BaseModel):
    transfer_ref: str | None = None
    notes: str | None = None


class ComplaintActionRequest(BaseModel):
    action: str = Field(description="resolved | dismissed | reviewing")
    admin_action: str = Field(min_length=3, max_length=1000)


# ------------------------------------------------------------------ helpers
def serialize_gym_for_rag(db, gym: Gym) -> dict[str, Any]:
    """Shape a DB gym exactly like the dataset JSON so the RAG builders work."""
    plans = db.query(GymPlan).filter(GymPlan.gym_id == gym.id).all()
    coaches = db.query(Coach).filter(Coach.gym_id == gym.id).all()
    equipment = db.query(Equipment).filter(Equipment.gym_id == gym.id).all()

    fee_with_coach = gym.monthly_fee + (0 if gym.coach_included else gym.coach_fee_separate)
    return {
        "gym_id": gym.gym_code,
        "name": gym.name,
        "slug": gym.slug or gym.gym_code.lower(),
        "tier": gym.tier or "standard",
        "gym_type": gym.gym_type or "Unisex",
        "description": gym.description or "",
        "location": {
            "address_line": gym.address_line or "",
            "locality": gym.locality or "",
            "locality_type": "town",
            "district": gym.district or "",
            "state": gym.state or "Andhra Pradesh",
            "pincode": gym.pincode or "",
            "latitude": gym.latitude or 0.0,
            "longitude": gym.longitude or 0.0,
            "distance_from_kakinada_km": _distance_from_kakinada(gym),
            "google_maps_url": gym.google_maps_url or "",
        },
        "contact": {
            "phone": gym.phone or "", "alt_phone": gym.alt_phone,
            "email": gym.email or "", "website": gym.website,
            "instagram": gym.instagram,
        },
        "timings": {
            "morning_open": gym.morning_open or "", "morning_close": gym.morning_close or "",
            "evening_open": gym.evening_open or "", "evening_close": gym.evening_close or "",
            "open_days": gym.open_days or "", "weekly_off": gym.weekly_off,
            "ladies_timing": gym.ladies_timing,
        },
        "pricing": {
            "currency": "INR",
            "monthly_fee": gym.monthly_fee,
            "registration_fee": gym.registration_fee or 0,
            "coach_included": gym.coach_included,
            "coach_fee_separate": gym.coach_fee_separate or 0,
            "coach_fee_note": ("Personal coaching is included in the membership fee."
                               if gym.coach_included else
                               f"Personal coach available at an extra Rs.{gym.coach_fee_separate}/month."),
            "membership_with_coach": fee_with_coach,
            "membership_without_coach": gym.monthly_fee,
            "trial_available": gym.trial_available,
            "trial_days": gym.trial_days or 0,
            "plans": [{
                "plan_name": p.plan_name, "duration_months": p.duration_months,
                "price": p.price, "effective_monthly": p.effective_monthly or 0,
                "savings": p.savings or 0, "coach_included": p.coach_included,
            } for p in plans],
        },
        "is_air_conditioned": gym.is_air_conditioned,
        "ac_status": "AC" if gym.is_air_conditioned else "Non-AC",
        "supplements_available": gym.supplements_available,
        "facilities": gym.facilities or [],
        "equipment": [{
            "name": e.name, "category": e.category or "Other",
            "quantity": e.quantity or 1, "description": e.description or "",
            "image_url": e.image_url or "", "condition": e.condition or "Good",
        } for e in equipment],
        "coaches": [{
            "name": c.name, "gender": c.gender or "Male",
            "experience_years": c.experience_years or 0,
            "specialisations": c.specialisations or [],
            "certifications": c.certifications or [],
            "bio": c.bio or "", "photo_url": c.photo_url or "",
            "rating": c.rating or 0.0,
        } for c in coaches],
        "rating": gym.rating or 0.0,
        "review_count": gym.review_count or 0,
        "member_count": gym.member_count or 0,
        "established_year": gym.established_year or 2020,
        "cover_image": gym.cover_image or "",
        "gallery": gym.gallery or [],
        "verified": gym.verified,
        "data_source": gym.data_source or "owner_submitted",
        "status": "active" if gym.status is GymStatus.active else gym.status.value,
    }


def _distance_from_kakinada(gym: Gym) -> float:
    import math
    from ..core.config import settings
    if not gym.latitude:
        return 0.0
    R = 6371.0
    lat1, lon1 = settings.REGION_CENTER_LAT, settings.REGION_CENTER_LON
    dlat, dlon = math.radians(gym.latitude - lat1), math.radians(gym.longitude - lon1)
    a = (math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1))
         * math.cos(math.radians(gym.latitude)) * math.sin(dlon / 2) ** 2)
    return round(2 * R * math.asin(math.sqrt(a)), 2)


def _reindex(db, gym: Gym) -> bool:
    try:
        from ..rag.vector_store import GymVectorStore
        store = GymVectorStore.get()
        if gym.status is GymStatus.active:
            store.index_one(serialize_gym_for_rag(db, gym))
            gym.indexed_in_rag = True
        else:
            store.remove(gym.gym_code)
            gym.indexed_in_rag = False
        db.commit()
        return gym.indexed_in_rag
    except Exception:
        return False


def _log(db, admin_id: int, action: str, entity_type: str,
         entity_id: str, details: dict | None = None) -> None:
    db.add(AuditLog(actor_type="admin", actor_id=admin_id, action=action,
                    entity_type=entity_type, entity_id=str(entity_id),
                    details=details or {}))


# ---------------------------------------------------------------- dashboard
@router.get("/dashboard")
def dashboard(db: DbSession, admin: CurrentAdmin):
    now = datetime.utcnow()

    total_collected = (db.query(func.coalesce(func.sum(Payment.amount), 0))
                       .filter(Payment.status == PaymentStatus.success).scalar() or 0)
    total_commission = (db.query(func.coalesce(func.sum(Payment.platform_commission), 0))
                        .filter(Payment.status == PaymentStatus.success).scalar() or 0)
    owed_to_gyms = (db.query(func.coalesce(func.sum(Payment.gym_share), 0))
                    .filter(Payment.status == PaymentStatus.success,
                            Payment.payout_id.is_(None)).scalar() or 0)
    paid_out = (db.query(func.coalesce(func.sum(Payout.net_payable), 0))
                .filter(Payout.status == PayoutStatus.paid).scalar() or 0)
    month_revenue = (db.query(func.coalesce(func.sum(Payment.amount), 0))
                     .filter(Payment.status == PaymentStatus.success,
                             func.strftime("%Y-%m", Payment.completed_at)
                             == now.strftime("%Y-%m")).scalar() or 0)

    overdue_rows = (db.query(Membership)
                    .filter(Membership.status == MembershipStatus.overdue).all())
    pending_amount = sum((m.base_fee or 0) + (m.coach_fee or 0) for m in overdue_rows)

    return {
        "counts": {
            "users": db.query(func.count(User.id))
                       .filter(User.status != UserStatus.deleted).scalar(),
            "blocked_users": db.query(func.count(User.id))
                               .filter(User.status == UserStatus.blocked).scalar(),
            "gym_owners": db.query(func.count(GymOwner.id)).scalar(),
            "gyms_total": db.query(func.count(Gym.id)).scalar(),
            "gyms_active": db.query(func.count(Gym.id))
                             .filter(Gym.status == GymStatus.active).scalar(),
            "gyms_pending": db.query(func.count(Gym.id))
                              .filter(Gym.status == GymStatus.pending_approval).scalar(),
            "memberships": db.query(func.count(Membership.id)).scalar(),
            "active_memberships": db.query(func.count(Membership.id))
                                    .filter(Membership.status == MembershipStatus.active).scalar(),
            "due_memberships": db.query(func.count(Membership.id))
                                 .filter(Membership.status == MembershipStatus.due).scalar(),
            "overdue_memberships": len(overdue_rows),
            "open_complaints": db.query(func.count(Complaint.id))
                                 .filter(Complaint.status == "open").scalar(),
        },
        "money": {
            "total_collected": int(total_collected),
            "platform_commission": int(total_commission),
            "owed_to_gyms": int(owed_to_gyms),
            "already_paid_out": int(paid_out),
            "this_month_revenue": int(month_revenue),
            "pending_dues_amount": int(pending_amount),
        },
        "recent_payments": [{
            "payment_ref": p.payment_ref, "amount": p.amount,
            "commission": p.platform_commission, "gym_share": p.gym_share,
            "status": p.status.value,
            "completed_at": p.completed_at.isoformat() if p.completed_at else None,
            "gym": (db.get(Gym, p.gym_id).name if db.get(Gym, p.gym_id) else None),
            "user": (db.get(User, p.user_id).full_name if db.get(User, p.user_id) else None),
        } for p in db.query(Payment)
                     .filter(Payment.status == PaymentStatus.success)
                     .order_by(Payment.completed_at.desc()).limit(10).all()],
        "top_gyms": [{
            "gym_code": g.gym_code, "name": g.name, "locality": g.locality,
            "member_count": g.member_count, "rating": g.rating,
            "monthly_fee": g.monthly_fee,
        } for g in db.query(Gym).filter(Gym.status == GymStatus.active)
                     .order_by(Gym.member_count.desc()).limit(8).all()],
    }


# -------------------------------------------------------------------- users
@router.get("/users")
def list_users(db: DbSession, admin: CurrentAdmin,
               q: str | None = None, status_filter: str | None = None,
               page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    query = db.query(User).filter(User.status != UserStatus.deleted)
    if q:
        like = f"%{q}%"
        query = query.filter(func.lower(User.full_name).like(like.lower())
                             | User.email.like(like) | User.phone.like(like))
    if status_filter:
        try:
            query = query.filter(User.status == UserStatus(status_filter))
        except ValueError:
            pass

    total = query.count()
    rows = (query.order_by(User.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size).all())

    out = []
    for u in rows:
        ms = db.query(Membership).filter(Membership.user_id == u.id).all()
        spent = (db.query(func.coalesce(func.sum(Payment.amount), 0))
                 .filter(Payment.user_id == u.id,
                         Payment.status == PaymentStatus.success).scalar() or 0)
        out.append({
            "id": u.id, "full_name": u.full_name, "email": u.email,
            "phone": u.phone, "locality": u.locality, "district": u.district,
            "photo_url": u.photo_url, "status": u.status.value,
            "email_verified": u.email_verified,
            "blocked_reason": u.blocked_reason,
            "created_at": u.created_at.isoformat() if u.created_at else None,
            "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
            "membership_count": len(ms),
            "active_memberships": sum(1 for m in ms
                                      if m.status is MembershipStatus.active),
            "overdue_memberships": sum(1 for m in ms
                                       if m.status is MembershipStatus.overdue),
            "total_spent": int(spent),
        })
    return {"users": out, "total": total, "page": page, "page_size": page_size}


@router.get("/users/{user_id}")
def user_detail(user_id: int, db: DbSession, admin: CurrentAdmin):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    memberships = db.query(Membership).filter(Membership.user_id == u.id).all()
    payments = (db.query(Payment).filter(Payment.user_id == u.id)
                .order_by(Payment.created_at.desc()).all())

    return {
        "user": {
            "id": u.id, "full_name": u.full_name, "email": u.email,
            "phone": u.phone, "address": u.address, "locality": u.locality,
            "district": u.district, "pincode": u.pincode,
            "latitude": u.latitude, "longitude": u.longitude,
            "date_of_birth": u.date_of_birth.isoformat() if u.date_of_birth else None,
            "gender": u.gender, "height_cm": u.height_cm, "weight_kg": u.weight_kg,
            "fitness_goal": u.fitness_goal.value if u.fitness_goal else None,
            "medical_notes": u.medical_notes, "photo_url": u.photo_url,
            "status": u.status.value, "blocked_reason": u.blocked_reason,
            "email_verified": u.email_verified,
            "created_at": u.created_at.isoformat() if u.created_at else None,
        },
        "memberships": [{
            "membership_code": m.membership_code, "status": m.status.value,
            "gym": (lambda g: {"gym_code": g.gym_code, "name": g.name} if g else None)(
                db.get(Gym, m.gym_id)),
            "total_amount": m.total_amount,
            "start_date": m.start_date.isoformat() if m.start_date else None,
            "end_date": m.end_date.isoformat() if m.end_date else None,
            "due_info": (lambda i: i.as_dict() if i else None)(evaluate(m)),
        } for m in memberships],
        "payments": [{
            "payment_ref": p.payment_ref, "amount": p.amount,
            "status": p.status.value, "method": p.method,
            "completed_at": p.completed_at.isoformat() if p.completed_at else None,
        } for p in payments],
        "complaints_against": [{
            "id": c.id, "subject": c.subject, "category": c.category,
            "status": c.status, "created_at": c.created_at.isoformat(),
        } for c in db.query(Complaint)
                     .filter(Complaint.against_user_id == u.id).all()],
    }


@router.post("/users/{user_id}/block")
def block_user(user_id: int, payload: BlockRequest, db: DbSession, admin: CurrentAdmin):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    u.status = UserStatus.blocked
    u.blocked_reason = payload.reason
    # their passes stop scanning immediately
    for m in db.query(Membership).filter(Membership.user_id == u.id).all():
        ep = db.query(EntryPass).filter(EntryPass.membership_id == m.id).first()
        if ep:
            ep.is_active = False

    _log(db, admin.id, "block_user", "user", user_id, {"reason": payload.reason})
    db.commit()
    return {"success": True, "user_id": user_id, "status": "blocked",
            "message": f"{u.full_name} is blocked and their entry passes are disabled."}


@router.post("/users/{user_id}/unblock")
def unblock_user(user_id: int, db: DbSession, admin: CurrentAdmin):
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    u.status = UserStatus.active
    u.blocked_reason = None
    for m in (db.query(Membership)
              .filter(Membership.user_id == u.id,
                      Membership.status.in_([MembershipStatus.active,
                                             MembershipStatus.due])).all()):
        ep = db.query(EntryPass).filter(EntryPass.membership_id == m.id).first()
        if ep:
            ep.is_active = True

    _log(db, admin.id, "unblock_user", "user", user_id)
    db.commit()
    return {"success": True, "user_id": user_id, "status": "active"}


@router.delete("/users/{user_id}")
def delete_user(user_id: int, db: DbSession, admin: CurrentAdmin):
    """Soft delete - payment history must survive for accounting."""
    u = db.get(User, user_id)
    if not u:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    u.status = UserStatus.deleted
    for m in db.query(Membership).filter(Membership.user_id == u.id).all():
        m.status = MembershipStatus.removed
        ep = db.query(EntryPass).filter(EntryPass.membership_id == m.id).first()
        if ep:
            ep.is_active = False

    _log(db, admin.id, "delete_user", "user", user_id)
    db.commit()
    return {"success": True, "user_id": user_id, "status": "deleted"}


# --------------------------------------------------------------------- gyms
@router.get("/gyms")
def list_gyms(db: DbSession, admin: CurrentAdmin,
              q: str | None = None, status_filter: str | None = None,
              page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    query = db.query(Gym)
    if q:
        like = f"%{q}%"
        query = query.filter(Gym.name.ilike(like) | Gym.locality.ilike(like)
                             | Gym.gym_code.ilike(like))
    if status_filter:
        try:
            query = query.filter(Gym.status == GymStatus(status_filter))
        except ValueError:
            pass

    total = query.count()
    rows = (query.order_by(Gym.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size).all())

    out = []
    for g in rows:
        owner = db.get(GymOwner, g.owner_id) if g.owner_id else None
        collected = (db.query(func.coalesce(func.sum(Payment.gym_share), 0))
                     .filter(Payment.gym_id == g.id,
                             Payment.status == PaymentStatus.success).scalar() or 0)
        out.append({
            "id": g.id, "gym_code": g.gym_code, "name": g.name,
            "locality": g.locality, "district": g.district,
            "monthly_fee": g.monthly_fee, "coach_included": g.coach_included,
            "coach_fee_separate": g.coach_fee_separate,
            "ac_status": "AC" if g.is_air_conditioned else "Non-AC",
            "gym_type": g.gym_type, "rating": g.rating,
            "member_count": g.member_count,
            "status": g.status.value, "verified": g.verified,
            "indexed_in_rag": g.indexed_in_rag,
            "data_source": g.data_source,
            "created_by_admin": g.created_by_admin,
            "commission_percent": g.commission_percent,
            "owner": ({"id": owner.id, "name": owner.full_name,
                       "email": owner.email, "phone": owner.phone}
                      if owner else None),
            "lifetime_gym_share": int(collected),
        })
    return {"gyms": out, "total": total, "page": page, "page_size": page_size}


@router.post("/gyms", status_code=status.HTTP_201_CREATED)
def create_gym(payload: AdminGymRequest, db: DbSession, admin: CurrentAdmin):
    """
    Admin adds a gym manually - e.g. a gym in a village that has no partner
    account yet. Optionally creates the owner login at the same time.
    """
    owner = None
    if payload.create_owner_account:
        if not (payload.owner_email and payload.owner_password):
            raise HTTPException(status.HTTP_400_BAD_REQUEST,
                                "Owner email and password are required to create a partner login.")
        email = payload.owner_email.lower().strip()
        if db.query(GymOwner).filter(func.lower(GymOwner.email) == email).first():
            raise HTTPException(status.HTTP_409_CONFLICT,
                                "A partner account with this email already exists.")
        owner = GymOwner(
            full_name=payload.owner_name or f"{payload.name} Owner",
            email=email,
            phone=payload.owner_phone or payload.phone,
            password_hash=hash_password(payload.owner_password),
            business_name=payload.name,
            email_verified=True,
            status=UserStatus.active,
        )
        db.add(owner)
        db.flush()

    gym = Gym(
        gym_code=generate_code("FIT", 7),
        owner_id=owner.id if owner else None,
        created_by_admin=True,
        data_source="admin_entered",
        status=GymStatus.active if payload.publish else GymStatus.draft,
        verified=True,
    )

    # Populate every column BEFORE the row reaches the database - `name` and
    # the other NOT NULL columns are only known from the payload.
    skip = {"create_owner_account", "owner_name", "owner_email",
            "owner_phone", "owner_password", "publish"}
    for field, value in payload.model_dump().items():
        if field not in skip:
            setattr(gym, field, value)

    db.add(gym)
    db.flush()

    gym.slug = (payload.name.lower().replace(" ", "-").replace(",", "")
                .replace("'", "").replace("&", "and").replace(".", "")
                + f"-{gym.gym_code.lower()}")
    gym.google_maps_url = (f"https://www.google.com/maps/search/?api=1"
                           f"&query={payload.latitude},{payload.longitude}")
    gym.tier = ("ladies" if payload.gym_type == "Ladies Only" else
                "premium" if payload.monthly_fee >= 2200 else
                "standard" if payload.monthly_fee >= 1200 else "budget")
    db.commit()

    # standard plan ladder
    ladder = [("Monthly", 1, 1.00), ("Quarterly", 3, 0.90),
              ("Half-Yearly", 6, 0.82), ("Annual", 12, 0.70)]
    for label, months, mult in ladder:
        total = int(round(payload.monthly_fee * months * mult / 10) * 10)
        db.add(GymPlan(
            gym_id=gym.id, plan_name=label, duration_months=months, price=total,
            effective_monthly=int(round(total / months)),
            savings=int(round(payload.monthly_fee * months - total)),
            coach_included=payload.coach_included,
        ))
    db.commit()

    indexed = _reindex(db, gym)
    _log(db, admin.id, "create_gym", "gym", gym.gym_code,
         {"name": gym.name, "locality": gym.locality, "indexed": indexed})
    db.commit()

    return {
        "success": True,
        "gym_id": gym.id,
        "gym_code": gym.gym_code,
        "status": gym.status.value,
        "indexed_in_rag": indexed,
        "owner_created": owner is not None,
        "owner_login": ({"email": owner.email, "password": "(as you set it)"}
                        if owner else None),
        "message": (f"{gym.name} added"
                    + (" and is now discoverable in the chatbot." if indexed
                       else " as a draft.")),
    }


@router.put("/gyms/{gym_id}")
def update_gym(gym_id: int, payload: AdminGymRequest, db: DbSession, admin: CurrentAdmin):
    gym = db.get(Gym, gym_id)
    if not gym:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Gym not found")

    skip = {"create_owner_account", "owner_name", "owner_email",
            "owner_phone", "owner_password", "publish"}
    for field, value in payload.model_dump().items():
        if field not in skip:
            setattr(gym, field, value)
    gym.status = GymStatus.active if payload.publish else GymStatus.draft
    gym.google_maps_url = (f"https://www.google.com/maps/search/?api=1"
                           f"&query={payload.latitude},{payload.longitude}")
    db.commit()

    indexed = _reindex(db, gym)
    _log(db, admin.id, "update_gym", "gym", gym.gym_code, {"indexed": indexed})
    db.commit()
    return {"success": True, "gym_code": gym.gym_code,
            "status": gym.status.value, "indexed_in_rag": indexed}


@router.post("/gyms/{gym_id}/approve")
def approve_gym(gym_id: int, db: DbSession, admin: CurrentAdmin):
    gym = db.get(Gym, gym_id)
    if not gym:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Gym not found")
    gym.status = GymStatus.active
    gym.verified = True
    indexed = _reindex(db, gym)
    _log(db, admin.id, "approve_gym", "gym", gym.gym_code)
    db.commit()
    return {"success": True, "gym_code": gym.gym_code,
            "status": "active", "indexed_in_rag": indexed}


@router.post("/gyms/{gym_id}/suspend")
def suspend_gym(gym_id: int, payload: BlockRequest, db: DbSession, admin: CurrentAdmin):
    gym = db.get(Gym, gym_id)
    if not gym:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Gym not found")
    gym.status = GymStatus.suspended
    _reindex(db, gym)      # removes it from the chatbot index
    _log(db, admin.id, "suspend_gym", "gym", gym.gym_code, {"reason": payload.reason})
    db.commit()
    return {"success": True, "gym_code": gym.gym_code, "status": "suspended",
            "message": "Gym suspended and removed from search results."}


# --------------------------------------------------------------------- dues
@router.get("/dues")
def all_dues(db: DbSession, admin: CurrentAdmin,
             gym_id: int | None = None, state: str | None = None):
    q = (db.query(Membership, User, Gym)
         .join(User, User.id == Membership.user_id)
         .join(Gym, Gym.id == Membership.gym_id)
         .filter(Membership.status.in_([MembershipStatus.active,
                                        MembershipStatus.due,
                                        MembershipStatus.overdue])))
    if gym_id:
        q = q.filter(Membership.gym_id == gym_id)

    out = []
    for m, u, g in q.all():
        info = evaluate(m)
        if info is None or info.state == "upcoming":
            continue
        if state and info.state != state:
            continue
        out.append({
            **info.as_dict(),
            "user": {"id": u.id, "name": u.full_name, "phone": u.phone,
                     "email": u.email, "photo_url": u.photo_url,
                     "status": u.status.value},
            "gym": {"id": g.id, "gym_code": g.gym_code, "name": g.name,
                    "locality": g.locality},
        })

    out.sort(key=lambda r: -r["days_overdue"])
    return {
        "dues": out,
        "total": len(out),
        "total_pending_amount": sum(r["amount"] for r in out),
        "by_state": {
            "due": sum(1 for r in out if r["state"] == "due"),
            "overdue": sum(1 for r in out if r["state"] == "overdue"),
        },
        "permissions": {"can_extend_grace": True, "can_remove_member": True},
    }


@router.post("/dues/{membership_id}/extend-grace")
def extend_member_grace(membership_id: int, payload: GracePeriodRequest,
                        db: DbSession, admin: CurrentAdmin):
    try:
        result = extend_grace(db, membership_id, payload.extra_days,
                              admin.id, payload.reason)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    return {"success": True, **result,
            "message": f"Grace period extended by {payload.extra_days} days."}


@router.post("/dues/{membership_id}/remove-member")
def remove_defaulting_member(membership_id: int, payload: RemoveMemberRequest,
                             db: DbSession, admin: CurrentAdmin):
    try:
        result = remove_member(db, membership_id, admin.id, payload.reason)
    except ValueError as e:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(e))
    return {"success": True, **result,
            "message": "Member removed and their entry pass deactivated."}


@router.post("/dues/run-sweep")
def run_sweep(db: DbSession, admin: CurrentAdmin, send_warnings: bool = True):
    """Re-classify every membership and send pending warnings. Safe to re-run."""
    stats = run_daily_sweep(db, send_warnings=send_warnings)
    _log(db, admin.id, "run_dues_sweep", "system", "dues", stats)
    db.commit()
    return {"success": True, **stats}


# ----------------------------------------------------------------- payments
@router.get("/payments")
def list_payments(db: DbSession, admin: CurrentAdmin,
                  gym_id: int | None = None, status_filter: str | None = None,
                  page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
    q = db.query(Payment)
    if gym_id:
        q = q.filter(Payment.gym_id == gym_id)
    if status_filter:
        try:
            q = q.filter(Payment.status == PaymentStatus(status_filter))
        except ValueError:
            pass

    total = q.count()
    rows = (q.order_by(Payment.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size).all())

    return {
        "payments": [{
            "payment_ref": p.payment_ref, "amount": p.amount,
            "platform_commission": p.platform_commission,
            "gym_share": p.gym_share, "method": p.method,
            "gateway": p.gateway, "gateway_txn_id": p.gateway_txn_id,
            "status": p.status.value, "settled": p.payout_id is not None,
            "created_at": p.created_at.isoformat() if p.created_at else None,
            "completed_at": p.completed_at.isoformat() if p.completed_at else None,
            "user": (lambda u: {"id": u.id, "name": u.full_name} if u else None)(
                db.get(User, p.user_id)),
            "gym": (lambda g: {"gym_code": g.gym_code, "name": g.name} if g else None)(
                db.get(Gym, p.gym_id)),
        } for p in rows],
        "total": total, "page": page, "page_size": page_size,
    }


# ------------------------------------------------------------------ payouts
@router.get("/payouts")
def list_payouts(db: DbSession, admin: CurrentAdmin, status_filter: str | None = None):
    q = db.query(Payout)
    if status_filter:
        try:
            q = q.filter(Payout.status == PayoutStatus(status_filter))
        except ValueError:
            pass
    rows = q.order_by(Payout.period_year.desc(), Payout.period_month.desc()).all()

    return {"payouts": [{
        "id": p.id, "payout_ref": p.payout_ref,
        "period": f"{p.period_year}-{p.period_month:02d}",
        "gross_collected": p.gross_collected,
        "platform_commission": p.platform_commission,
        "net_payable": p.net_payable, "payment_count": p.payment_count,
        "status": p.status.value, "transfer_ref": p.transfer_ref,
        "paid_at": p.paid_at.isoformat() if p.paid_at else None,
        "gym": (lambda g: {"gym_code": g.gym_code, "name": g.name} if g else None)(
            db.get(Gym, p.gym_id)),
        "owner": (lambda o: {"name": o.full_name, "email": o.email,
                             "bank_account": (f"****{o.bank_account_number[-4:]}"
                                              if o.bank_account_number else None),
                             "ifsc": o.bank_ifsc, "upi_id": o.upi_id} if o else None)(
            db.get(GymOwner, p.owner_id)),
    } for p in rows]}


@router.get("/payouts/pending")
def pending_payouts(db: DbSession, admin: CurrentAdmin,
                    month: int | None = None, year: int | None = None):
    """Unsettled gym shares, grouped by gym - what the admin owes right now."""
    now = datetime.utcnow()
    month = month or now.month
    year = year or now.year
    period = f"{year}-{month:02d}"

    rows = (db.query(Payment)
            .filter(Payment.status == PaymentStatus.success,
                    Payment.payout_id.is_(None),
                    func.strftime("%Y-%m", Payment.completed_at) == period)
            .all())

    grouped: dict[int, dict[str, Any]] = {}
    for p in rows:
        g = grouped.setdefault(p.gym_id, {
            "gym_id": p.gym_id, "gross": 0, "commission": 0,
            "net": 0, "count": 0,
        })
        g["gross"] += p.amount
        g["commission"] += p.platform_commission or 0
        g["net"] += p.gym_share or 0
        g["count"] += 1

    out = []
    for gid, v in grouped.items():
        gym = db.get(Gym, gid)
        owner = db.get(GymOwner, gym.owner_id) if gym and gym.owner_id else None
        existing = (db.query(Payout)
                    .filter(Payout.gym_id == gid, Payout.period_month == month,
                            Payout.period_year == year).first())
        out.append({
            **v,
            "gym": {"gym_code": gym.gym_code, "name": gym.name,
                    "locality": gym.locality} if gym else None,
            "owner": ({"id": owner.id, "name": owner.full_name,
                       "email": owner.email,
                       "bank_configured": bool(owner.bank_account_number or owner.upi_id),
                       "bank_account": (f"****{owner.bank_account_number[-4:]}"
                                        if owner.bank_account_number else None),
                       "ifsc": owner.bank_ifsc, "upi_id": owner.upi_id}
                      if owner else None),
            "payout_exists": existing is not None,
            "payout_status": existing.status.value if existing else None,
        })

    out.sort(key=lambda x: -x["net"])
    return {
        "period": period,
        "gyms": out,
        "totals": {
            "gross": sum(x["gross"] for x in out),
            "commission": sum(x["commission"] for x in out),
            "net_payable": sum(x["net"] for x in out),
            "gym_count": len(out),
        },
    }


@router.post("/payouts", status_code=status.HTTP_201_CREATED)
def create_payout(payload: PayoutRequest, db: DbSession, admin: CurrentAdmin):
    gym = db.get(Gym, payload.gym_id)
    if not gym:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Gym not found")

    existing = (db.query(Payout)
                .filter(Payout.gym_id == gym.id,
                        Payout.period_month == payload.period_month,
                        Payout.period_year == payload.period_year).first())
    if existing:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"A payout for {payload.period_year}-{payload.period_month:02d} "
                            f"already exists ({existing.payout_ref}).")

    period = f"{payload.period_year}-{payload.period_month:02d}"
    payments = (db.query(Payment)
                .filter(Payment.gym_id == gym.id,
                        Payment.status == PaymentStatus.success,
                        Payment.payout_id.is_(None),
                        func.strftime("%Y-%m", Payment.completed_at) == period)
                .all())
    if not payments:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"No unsettled payments for {gym.name} in {period}.")

    gross = sum(p.amount for p in payments)
    commission = sum(p.platform_commission or 0 for p in payments)
    net = sum(p.gym_share or 0 for p in payments)

    payout = Payout(
        payout_ref=generate_code("FTPO", 10),
        gym_id=gym.id, owner_id=gym.owner_id,
        period_month=payload.period_month, period_year=payload.period_year,
        gross_collected=gross, platform_commission=commission,
        net_payable=net, payment_count=len(payments),
        status=PayoutStatus.scheduled,
        scheduled_for=date.today(),
        processed_by_admin_id=admin.id,
    )
    db.add(payout)
    db.flush()
    for p in payments:
        p.payout_id = payout.id

    _log(db, admin.id, "create_payout", "payout", payout.payout_ref,
         {"gym": gym.gym_code, "period": period, "net": net})
    db.commit()

    return {"success": True, "payout_ref": payout.payout_ref,
            "gym": gym.name, "period": period,
            "gross_collected": gross, "platform_commission": commission,
            "net_payable": net, "payment_count": len(payments),
            "status": payout.status.value}


@router.post("/payouts/{payout_id}/release")
def release_payout(payout_id: int, payload: PayoutReleaseRequest,
                   db: DbSession, admin: CurrentAdmin):
    """Mark the transfer to the gym owner's bank account as done."""
    payout = db.get(Payout, payout_id)
    if not payout:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payout not found")
    if payout.status is PayoutStatus.paid:
        raise HTTPException(status.HTTP_409_CONFLICT, "This payout is already paid.")

    payout.status = PayoutStatus.paid
    payout.paid_at = datetime.utcnow()
    payout.transfer_ref = payload.transfer_ref or generate_code("NEFT", 12)
    payout.notes = payload.notes
    payout.processed_by_admin_id = admin.id

    _log(db, admin.id, "release_payout", "payout", payout.payout_ref,
         {"amount": payout.net_payable, "transfer_ref": payout.transfer_ref})
    db.commit()

    gym = db.get(Gym, payout.gym_id)
    return {"success": True, "payout_ref": payout.payout_ref,
            "status": "paid", "transfer_ref": payout.transfer_ref,
            "amount": payout.net_payable,
            "message": f"Rs.{payout.net_payable} released to {gym.name if gym else 'gym'}."}


# -------------------------------------------------------------- complaints
@router.get("/complaints")
def list_complaints(db: DbSession, admin: CurrentAdmin, status_filter: str | None = None):
    q = db.query(Complaint)
    if status_filter:
        q = q.filter(Complaint.status == status_filter)
    rows = q.order_by(Complaint.created_at.desc()).all()

    return {"complaints": [{
        "id": c.id, "subject": c.subject, "category": c.category,
        "details": c.details, "status": c.status, "admin_action": c.admin_action,
        "created_at": c.created_at.isoformat(),
        "resolved_at": c.resolved_at.isoformat() if c.resolved_at else None,
        "gym": (lambda g: {"gym_code": g.gym_code, "name": g.name} if g else None)(
            db.get(Gym, c.gym_id)),
        "against_user": (lambda u: {"id": u.id, "name": u.full_name,
                                    "phone": u.phone, "status": u.status.value}
                         if u else None)(db.get(User, c.against_user_id)),
        "raised_by": (lambda o: {"name": o.full_name, "email": o.email}
                      if o else None)(db.get(GymOwner, c.raised_by_owner_id)),
    } for c in rows]}


@router.post("/complaints/{complaint_id}/action")
def act_on_complaint(complaint_id: int, payload: ComplaintActionRequest,
                     db: DbSession, admin: CurrentAdmin):
    c = db.get(Complaint, complaint_id)
    if not c:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Complaint not found")

    c.status = payload.action
    c.admin_action = payload.admin_action
    c.resolved_by_admin_id = admin.id
    if payload.action in ("resolved", "dismissed"):
        c.resolved_at = datetime.utcnow()

    _log(db, admin.id, "complaint_action", "complaint", complaint_id,
         {"action": payload.action})
    db.commit()
    return {"success": True, "complaint_id": complaint_id, "status": c.status}


# ------------------------------------------------------------------- audit
@router.get("/audit-logs")
def audit_logs(db: DbSession, admin: CurrentAdmin,
               action: str | None = None, page: int = Query(1, ge=1),
               page_size: int = Query(50, ge=1, le=200)):
    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action == action)
    total = q.count()
    rows = (q.order_by(AuditLog.created_at.desc())
            .offset((page - 1) * page_size).limit(page_size).all())
    return {"logs": [{
        "id": l.id, "actor_type": l.actor_type, "actor_id": l.actor_id,
        "action": l.action, "entity_type": l.entity_type,
        "entity_id": l.entity_id, "details": l.details,
        "created_at": l.created_at.isoformat(),
    } for l in rows], "total": total, "page": page}


# ---------------------------------------------------------------- RAG index
@router.post("/rag/reindex")
def reindex_all(db: DbSession, admin: CurrentAdmin):
    """Rebuild the whole vector index from the live database."""
    from ..rag.vector_store import GymVectorStore

    gyms = db.query(Gym).filter(Gym.status == GymStatus.active).all()
    payload = [serialize_gym_for_rag(db, g) for g in gyms]
    count = GymVectorStore.get().index_gyms(payload, reset=True)

    for g in gyms:
        g.indexed_in_rag = True
    _log(db, admin.id, "rag_reindex", "system", "rag", {"count": count})
    db.commit()
    return {"success": True, "indexed": count,
            "message": f"{count} gyms re-indexed for the chatbot."}


@router.get("/rag/status")
def rag_status(db: DbSession, admin: CurrentAdmin):
    from ..core.config import settings
    from ..rag.chatbot import FitoraChatbot
    from ..rag.vector_store import GymVectorStore

    store = GymVectorStore.get()
    active = db.query(func.count(Gym.id)).filter(Gym.status == GymStatus.active).scalar()
    bot = FitoraChatbot(model=settings.OLLAMA_MODEL, host=settings.OLLAMA_HOST)

    return {
        "indexed_gyms": store.count(),
        "active_gyms_in_db": active,
        "in_sync": store.count() == active,
        "embedding_model": settings.EMBED_MODEL,
        "llm_model": settings.OLLAMA_MODEL,
        "llm_available": bot.available(),
    }
