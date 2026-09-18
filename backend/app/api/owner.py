"""
Fitora - Gym owner portal.

The owner manages their gym profile, pricing, coaches and equipment, and can
SEE members, reviews, dues and earnings. What they cannot do, by design:

  * they cannot collect money - every payment goes to the platform and comes
    back as an admin-released Payout
  * they cannot block, remove or edit a member - they raise a Complaint and
    the admin decides

Saving a profile re-indexes the gym in the RAG store, so it becomes
discoverable in the chatbot immediately.
"""
from __future__ import annotations
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import func

from ..core.security import generate_code
from ..db.models import (
    AuditLog, Coach, Complaint, Equipment, Gym, GymPlan, GymStatus,
    Membership, MembershipStatus, Payment, PaymentStatus, Payout, PayoutStatus,
    Review, User,
)
from ..services.dues_service import dues_for_gym, gym_payment_summary
from .deps import CurrentOwner, DbSession

router = APIRouter(prefix="/owner", tags=["gym-owner"])


# ------------------------------------------------------------------ schemas
class GymProfileRequest(BaseModel):
    name: str = Field(min_length=2, max_length=180)
    description: str | None = None
    gym_type: str = "Unisex"
    tier: str | None = None
    # location
    address_line: str
    locality: str
    district: str
    state: str = "Andhra Pradesh"
    pincode: str
    latitude: float
    longitude: float
    # contact
    phone: str
    alt_phone: str | None = None
    email: str | None = None
    website: str | None = None
    instagram: str | None = None
    # timings
    morning_open: str = "05:30"
    morning_close: str = "11:00"
    evening_open: str = "16:30"
    evening_close: str = "22:00"
    open_days: str = "Monday - Saturday"
    weekly_off: str | None = "Sunday"
    ladies_timing: str | None = None
    # pricing
    monthly_fee: int = Field(ge=0)
    registration_fee: int = Field(default=0, ge=0)
    coach_included: bool = False
    coach_fee_separate: int = Field(default=0, ge=0)
    trial_available: bool = False
    trial_days: int = Field(default=0, ge=0, le=30)
    # amenities
    is_air_conditioned: bool = False
    supplements_available: bool = False
    facilities: list[str] = Field(default_factory=list)
    established_year: int | None = None
    # media
    cover_image: str | None = None
    gallery: list[str] = Field(default_factory=list)


class PlanRequest(BaseModel):
    plan_name: str
    duration_months: int = Field(ge=1, le=36)
    price: int = Field(ge=0)
    coach_included: bool = False


class CoachRequest(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    gender: str = "Male"
    experience_years: int = Field(ge=0, le=60)
    specialisations: list[str] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    bio: str | None = None
    photo_url: str | None = None


class EquipmentRequest(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    category: str = "Strength Machines"
    quantity: int = Field(default=1, ge=1, le=200)
    description: str | None = None
    image_url: str | None = None      # the owner's ACTUAL photo
    condition: str = "Good"


class BankRequest(BaseModel):
    bank_account_name: str
    bank_account_number: str
    bank_ifsc: str
    upi_id: str | None = None


class ComplaintRequest(BaseModel):
    against_user_id: int
    membership_id: int | None = None
    category: str = "payment_default"
    subject: str = Field(min_length=3, max_length=200)
    details: str | None = None


# ------------------------------------------------------------------ helpers
def _owned_gym(db, owner, gym_id: int | None = None) -> Gym:
    q = db.query(Gym).filter(Gym.owner_id == owner.id)
    gym = q.filter(Gym.id == gym_id).first() if gym_id else q.first()
    if not gym:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            "No gym found for this partner account.")
    return gym


def _reindex(db, gym: Gym) -> bool:
    """Push the saved profile into the RAG store so the chatbot can find it."""
    if gym.status is not GymStatus.active:
        return False
    try:
        from ..rag.vector_store import GymVectorStore
        from .admin import serialize_gym_for_rag
        GymVectorStore.get().index_one(serialize_gym_for_rag(db, gym))
        gym.indexed_in_rag = True
        db.commit()
        return True
    except Exception:
        return False


def _rebuild_plans(db, gym: Gym) -> None:
    """Regenerate the standard plan ladder from the headline monthly fee."""
    db.query(GymPlan).filter(GymPlan.gym_id == gym.id).delete()
    ladder = [("Monthly", 1, 1.00), ("Quarterly", 3, 0.90),
              ("Half-Yearly", 6, 0.82), ("Annual", 12, 0.70)]
    base = gym.monthly_fee
    for label, months, mult in ladder:
        total = int(round(base * months * mult / 10) * 10)
        db.add(GymPlan(
            gym_id=gym.id, plan_name=label, duration_months=months, price=total,
            effective_monthly=int(round(total / months)),
            savings=int(round(base * months - total)),
            coach_included=gym.coach_included,
        ))
    if not gym.coach_included and gym.coach_fee_separate:
        for label, months, mult in [("Monthly + Personal Coach", 1, 1.00),
                                    ("Quarterly + Personal Coach", 3, 0.92)]:
            total = int(round((base + gym.coach_fee_separate) * months * mult / 10) * 10)
            db.add(GymPlan(
                gym_id=gym.id, plan_name=label, duration_months=months, price=total,
                effective_monthly=int(round(total / months)),
                savings=int(round((base + gym.coach_fee_separate) * months - total)),
                coach_included=True,
            ))
    db.commit()


# ---------------------------------------------------------------- dashboard
@router.get("/dashboard")
def dashboard(db: DbSession, owner: CurrentOwner):
    gyms = db.query(Gym).filter(Gym.owner_id == owner.id).all()
    if not gyms:
        return {"needs_onboarding": True, "gyms": [],
                "message": "Add your gym profile to start receiving members."}

    gym = gyms[0]
    summary = gym_payment_summary(db, gym.id)

    now = datetime.utcnow()
    month_collected = (db.query(func.coalesce(func.sum(Payment.gym_share), 0))
                       .filter(Payment.gym_id == gym.id,
                               Payment.status == PaymentStatus.success,
                               func.strftime("%Y-%m", Payment.completed_at)
                               == now.strftime("%Y-%m"))
                       .scalar() or 0)
    lifetime = (db.query(func.coalesce(func.sum(Payment.gym_share), 0))
                .filter(Payment.gym_id == gym.id,
                        Payment.status == PaymentStatus.success).scalar() or 0)
    paid_out = (db.query(func.coalesce(func.sum(Payout.net_payable), 0))
                .filter(Payout.gym_id == gym.id,
                        Payout.status == PayoutStatus.paid).scalar() or 0)

    recent = (db.query(Membership, User)
              .join(User, User.id == Membership.user_id)
              .filter(Membership.gym_id == gym.id)
              .order_by(Membership.created_at.desc()).limit(8).all())

    return {
        "needs_onboarding": gym.status is GymStatus.draft,
        "gym": {
            "id": gym.id, "gym_code": gym.gym_code, "name": gym.name,
            "status": gym.status.value, "verified": gym.verified,
            "indexed_in_rag": gym.indexed_in_rag,
            "cover_image": gym.cover_image, "locality": gym.locality,
            "rating": gym.rating, "review_count": gym.review_count,
        },
        "stats": {
            **summary,
            "equipment_count": db.query(func.count(Equipment.id))
                                 .filter(Equipment.gym_id == gym.id).scalar(),
            "coach_count": db.query(func.count(Coach.id))
                             .filter(Coach.gym_id == gym.id).scalar(),
            "plan_count": db.query(func.count(GymPlan.id))
                            .filter(GymPlan.gym_id == gym.id).scalar(),
        },
        "earnings": {
            "this_month_share": int(month_collected),
            "lifetime_share": int(lifetime),
            "already_paid_out": int(paid_out),
            "awaiting_payout": int(lifetime - paid_out),
            "commission_percent": gym.commission_percent,
            "note": ("Members pay Fitora. Your share is settled to your bank "
                     "account by the admin every month."),
        },
        "recent_members": [{
            "membership_code": m.membership_code, "name": u.full_name,
            "photo_url": u.photo_url, "status": m.status.value,
            "plan_amount": m.total_amount,
            "joined": m.start_date.isoformat() if m.start_date else None,
        } for m, u in recent],
        "all_gyms": [{"id": g.id, "gym_code": g.gym_code, "name": g.name,
                      "status": g.status.value} for g in gyms],
    }


# ------------------------------------------------------------- gym profile
@router.get("/gym")
def get_gym(db: DbSession, owner: CurrentOwner, gym_id: int | None = None):
    gym = _owned_gym(db, owner, gym_id)
    plans = db.query(GymPlan).filter(GymPlan.gym_id == gym.id) \
              .order_by(GymPlan.duration_months).all()
    return {
        "id": gym.id, "gym_code": gym.gym_code, "name": gym.name,
        "slug": gym.slug, "description": gym.description,
        "tier": gym.tier, "gym_type": gym.gym_type,
        "status": gym.status.value, "verified": gym.verified,
        "indexed_in_rag": gym.indexed_in_rag,
        "address_line": gym.address_line, "locality": gym.locality,
        "district": gym.district, "state": gym.state, "pincode": gym.pincode,
        "latitude": gym.latitude, "longitude": gym.longitude,
        "google_maps_url": gym.google_maps_url,
        "phone": gym.phone, "alt_phone": gym.alt_phone, "email": gym.email,
        "website": gym.website, "instagram": gym.instagram,
        "morning_open": gym.morning_open, "morning_close": gym.morning_close,
        "evening_open": gym.evening_open, "evening_close": gym.evening_close,
        "open_days": gym.open_days, "weekly_off": gym.weekly_off,
        "ladies_timing": gym.ladies_timing,
        "monthly_fee": gym.monthly_fee, "registration_fee": gym.registration_fee,
        "coach_included": gym.coach_included,
        "coach_fee_separate": gym.coach_fee_separate,
        "trial_available": gym.trial_available, "trial_days": gym.trial_days,
        "is_air_conditioned": gym.is_air_conditioned,
        "supplements_available": gym.supplements_available,
        "facilities": gym.facilities or [],
        "cover_image": gym.cover_image, "gallery": gym.gallery or [],
        "established_year": gym.established_year,
        "rating": gym.rating, "review_count": gym.review_count,
        "member_count": gym.member_count,
        "plans": [{"id": p.id, "plan_name": p.plan_name,
                   "duration_months": p.duration_months, "price": p.price,
                   "effective_monthly": p.effective_monthly,
                   "savings": p.savings, "coach_included": p.coach_included}
                  for p in plans],
    }


@router.put("/gym")
def save_gym(payload: GymProfileRequest, db: DbSession, owner: CurrentOwner,
             gym_id: int | None = None, submit: bool = True):
    """Create or update the gym profile. `submit=True` publishes it live."""
    gym = (db.query(Gym).filter(Gym.owner_id == owner.id, Gym.id == gym_id).first()
           if gym_id else db.query(Gym).filter(Gym.owner_id == owner.id).first())

    if not gym:
        gym = Gym(
            gym_code=generate_code("FIT", 7),
            owner_id=owner.id,
            status=GymStatus.draft,
            data_source="owner_submitted",
        )
        db.add(gym)
        db.flush()

    for field, value in payload.model_dump().items():
        setattr(gym, field, value)

    gym.slug = (payload.name.lower().replace(" ", "-").replace(",", "")
                .replace("'", "").replace("&", "and").replace(".", "")
                + f"-{gym.gym_code.lower()}")
    gym.google_maps_url = (f"https://www.google.com/maps/search/?api=1"
                           f"&query={payload.latitude},{payload.longitude}")
    if not gym.tier:
        gym.tier = ("premium" if payload.monthly_fee >= 2200 else
                    "standard" if payload.monthly_fee >= 1200 else "budget")
    if payload.gym_type == "Ladies Only":
        gym.tier = "ladies"

    if submit:
        gym.status = GymStatus.active

    db.commit()
    _rebuild_plans(db, gym)
    indexed = _reindex(db, gym)

    db.add(AuditLog(actor_type="gym_owner", actor_id=owner.id, action="gym_profile_saved",
                    entity_type="gym", entity_id=gym.gym_code,
                    details={"submitted": submit, "indexed": indexed}))
    db.commit()

    return {
        "success": True,
        "gym_id": gym.id,
        "gym_code": gym.gym_code,
        "status": gym.status.value,
        "indexed_in_rag": indexed,
        "message": ("Your gym is live and now discoverable in the Fitora chatbot."
                    if indexed else
                    "Profile saved. It will go live once activated."),
    }


@router.put("/bank")
def save_bank(payload: BankRequest, db: DbSession, owner: CurrentOwner):
    owner.bank_account_name = payload.bank_account_name
    owner.bank_account_number = payload.bank_account_number
    owner.bank_ifsc = payload.bank_ifsc
    owner.upi_id = payload.upi_id
    db.commit()
    return {"success": True,
            "message": "Payout details saved. Monthly settlements will go here."}


# ------------------------------------------------------------------- plans
@router.post("/plans", status_code=status.HTTP_201_CREATED)
def add_plan(payload: PlanRequest, db: DbSession, owner: CurrentOwner,
             gym_id: int | None = None):
    gym = _owned_gym(db, owner, gym_id)
    plan = GymPlan(
        gym_id=gym.id, plan_name=payload.plan_name,
        duration_months=payload.duration_months, price=payload.price,
        effective_monthly=int(round(payload.price / payload.duration_months)),
        savings=max(0, gym.monthly_fee * payload.duration_months - payload.price),
        coach_included=payload.coach_included,
    )
    db.add(plan)
    db.commit()
    _reindex(db, gym)
    return {"success": True, "plan_id": plan.id}


@router.delete("/plans/{plan_id}")
def delete_plan(plan_id: int, db: DbSession, owner: CurrentOwner):
    plan = db.get(GymPlan, plan_id)
    if not plan:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Plan not found")
    gym = _owned_gym(db, owner, plan.gym_id)
    db.delete(plan)
    db.commit()
    _reindex(db, gym)
    return {"success": True}


# ----------------------------------------------------------------- coaches
@router.get("/coaches")
def list_coaches(db: DbSession, owner: CurrentOwner, gym_id: int | None = None):
    gym = _owned_gym(db, owner, gym_id)
    rows = db.query(Coach).filter(Coach.gym_id == gym.id) \
             .order_by(Coach.experience_years.desc()).all()
    return {"coaches": [{
        "id": c.id, "name": c.name, "gender": c.gender,
        "experience_years": c.experience_years,
        "specialisations": c.specialisations or [],
        "certifications": c.certifications or [],
        "bio": c.bio, "photo_url": c.photo_url,
        "rating": c.rating, "is_active": c.is_active,
    } for c in rows], "total": len(rows)}


@router.post("/coaches", status_code=status.HTTP_201_CREATED)
def add_coach(payload: CoachRequest, db: DbSession, owner: CurrentOwner,
              gym_id: int | None = None):
    gym = _owned_gym(db, owner, gym_id)
    coach = Coach(gym_id=gym.id, **payload.model_dump())
    db.add(coach)
    db.commit()
    _reindex(db, gym)
    return {"success": True, "coach_id": coach.id}


@router.put("/coaches/{coach_id}")
def update_coach(coach_id: int, payload: CoachRequest, db: DbSession,
                 owner: CurrentOwner):
    coach = db.get(Coach, coach_id)
    if not coach:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Coach not found")
    gym = _owned_gym(db, owner, coach.gym_id)
    for k, v in payload.model_dump().items():
        setattr(coach, k, v)
    db.commit()
    _reindex(db, gym)
    return {"success": True}


@router.delete("/coaches/{coach_id}")
def delete_coach(coach_id: int, db: DbSession, owner: CurrentOwner):
    coach = db.get(Coach, coach_id)
    if not coach:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Coach not found")
    gym = _owned_gym(db, owner, coach.gym_id)
    db.delete(coach)
    db.commit()
    _reindex(db, gym)
    return {"success": True}


# --------------------------------------------------------------- equipment
@router.get("/equipment")
def list_equipment(db: DbSession, owner: CurrentOwner, gym_id: int | None = None):
    gym = _owned_gym(db, owner, gym_id)
    rows = db.query(Equipment).filter(Equipment.gym_id == gym.id) \
             .order_by(Equipment.category, Equipment.name).all()
    by_cat: dict[str, list[dict[str, Any]]] = {}
    for e in rows:
        by_cat.setdefault(e.category or "Other", []).append({
            "id": e.id, "name": e.name, "quantity": e.quantity,
            "description": e.description, "image_url": e.image_url,
            "condition": e.condition, "is_active": e.is_active,
        })
    return {
        "categories": by_cat,
        "total_items": len(rows),
        "total_units": sum(e.quantity or 1 for e in rows),
        "missing_images": sum(1 for e in rows if not e.image_url),
    }


@router.post("/equipment", status_code=status.HTTP_201_CREATED)
def add_equipment(payload: EquipmentRequest, db: DbSession, owner: CurrentOwner,
                  gym_id: int | None = None):
    gym = _owned_gym(db, owner, gym_id)
    eq = Equipment(gym_id=gym.id, **payload.model_dump())
    db.add(eq)
    db.commit()
    _reindex(db, gym)
    return {"success": True, "equipment_id": eq.id}


@router.put("/equipment/{equipment_id}")
def update_equipment(equipment_id: int, payload: EquipmentRequest,
                     db: DbSession, owner: CurrentOwner):
    eq = db.get(Equipment, equipment_id)
    if not eq:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Equipment not found")
    gym = _owned_gym(db, owner, eq.gym_id)
    for k, v in payload.model_dump().items():
        setattr(eq, k, v)
    db.commit()
    _reindex(db, gym)
    return {"success": True}


@router.delete("/equipment/{equipment_id}")
def delete_equipment(equipment_id: int, db: DbSession, owner: CurrentOwner):
    eq = db.get(Equipment, equipment_id)
    if not eq:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Equipment not found")
    gym = _owned_gym(db, owner, eq.gym_id)
    db.delete(eq)
    db.commit()
    _reindex(db, gym)
    return {"success": True}


# ----------------------------------------------------------------- members
@router.get("/members")
def members(db: DbSession, owner: CurrentOwner, gym_id: int | None = None,
            status_filter: str | None = None):
    from ..services.dues_service import evaluate

    gym = _owned_gym(db, owner, gym_id)
    q = (db.query(Membership, User)
         .join(User, User.id == Membership.user_id)
         .filter(Membership.gym_id == gym.id))
    if status_filter:
        try:
            q = q.filter(Membership.status == MembershipStatus(status_filter))
        except ValueError:
            pass

    rows = q.order_by(Membership.created_at.desc()).all()
    out = []
    for m, u in rows:
        info = evaluate(m)
        coach = db.get(Coach, m.assigned_coach_id) if m.assigned_coach_id else None
        out.append({
            "membership_code": m.membership_code,
            "membership_id": m.id,
            "user": {"id": u.id, "name": u.full_name, "phone": u.phone,
                     "email": u.email, "photo_url": u.photo_url,
                     "gender": u.gender},
            "goal": m.goal.value if m.goal else None,
            "weight_kg": m.weight_kg, "height_cm": m.height_cm,
            "with_coach": m.with_coach,
            "coach_name": coach.name if coach else None,
            "total_amount": m.total_amount,
            "status": m.status.value,
            "start_date": m.start_date.isoformat() if m.start_date else None,
            "end_date": m.end_date.isoformat() if m.end_date else None,
            "next_due_date": m.next_due_date.isoformat() if m.next_due_date else None,
            "due_info": info.as_dict() if info else None,
        })
    return {"members": out, "total": len(out),
            "gym": {"gym_code": gym.gym_code, "name": gym.name}}


# -------------------------------------------------------------------- dues
@router.get("/dues")
def dues(db: DbSession, owner: CurrentOwner, gym_id: int | None = None):
    """Read-only. The owner sees who has not paid; only the admin can act."""
    gym = _owned_gym(db, owner, gym_id)
    rows = dues_for_gym(db, gym.id)
    return {
        "gym": {"gym_code": gym.gym_code, "name": gym.name},
        "summary": gym_payment_summary(db, gym.id),
        "dues": rows,
        "permissions": {
            "can_view": True,
            "can_remove_member": False,
            "can_extend_grace": False,
            "can_raise_complaint": True,
            "note": ("Only the Fitora admin can extend a grace period or remove "
                     "a member. Raise a complaint and the admin will act on it."),
        },
    }


@router.post("/complaints", status_code=status.HTTP_201_CREATED)
def raise_complaint(payload: ComplaintRequest, db: DbSession, owner: CurrentOwner,
                    gym_id: int | None = None):
    gym = _owned_gym(db, owner, gym_id)

    # The target must actually be a member of THIS gym - otherwise any owner
    # could file a complaint (visible to the admin, tagged e.g.
    # "payment_default") against an arbitrary user with no relationship to
    # their gym, or reference a membership_id belonging to a different gym.
    membership = (db.query(Membership)
                  .filter(Membership.user_id == payload.against_user_id,
                          Membership.gym_id == gym.id)
                  .first())
    if not membership:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            "This user is not a member of your gym.")
    if payload.membership_id and payload.membership_id != membership.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "membership_id does not match this member's gym.")

    c = Complaint(
        gym_id=gym.id, raised_by_owner_id=owner.id,
        against_user_id=payload.against_user_id,
        membership_id=payload.membership_id,
        category=payload.category, subject=payload.subject,
        details=payload.details, status="open",
    )
    db.add(c)
    db.commit()
    return {"success": True, "complaint_id": c.id,
            "message": "Complaint sent to the Fitora admin for review."}


@router.get("/complaints")
def my_complaints(db: DbSession, owner: CurrentOwner):
    rows = (db.query(Complaint, User)
            .join(User, User.id == Complaint.against_user_id)
            .filter(Complaint.raised_by_owner_id == owner.id)
            .order_by(Complaint.created_at.desc()).all())
    return {"complaints": [{
        "id": c.id, "subject": c.subject, "category": c.category,
        "details": c.details, "status": c.status,
        "admin_action": c.admin_action,
        "against": {"id": u.id, "name": u.full_name},
        "created_at": c.created_at.isoformat(),
        "resolved_at": c.resolved_at.isoformat() if c.resolved_at else None,
    } for c, u in rows]}


# ----------------------------------------------------------------- reviews
@router.get("/reviews")
def reviews(db: DbSession, owner: CurrentOwner, gym_id: int | None = None):
    gym = _owned_gym(db, owner, gym_id)
    rows = (db.query(Review, User)
            .join(User, User.id == Review.user_id)
            .filter(Review.gym_id == gym.id)
            .order_by(Review.created_at.desc()).all())
    dist = {i: 0 for i in range(1, 6)}
    for r, _ in rows:
        dist[r.rating] = dist.get(r.rating, 0) + 1
    return {
        "rating": gym.rating, "review_count": gym.review_count,
        "distribution": dist,
        "reviews": [{
            "id": r.id, "rating": r.rating, "title": r.title, "comment": r.comment,
            "is_hidden": r.is_hidden,
            "user": {"name": u.full_name, "photo_url": u.photo_url},
            "created_at": r.created_at.isoformat(),
        } for r, u in rows],
    }


# ---------------------------------------------------------------- earnings
@router.get("/earnings")
def earnings(db: DbSession, owner: CurrentOwner, gym_id: int | None = None):
    gym = _owned_gym(db, owner, gym_id)

    payouts = (db.query(Payout).filter(Payout.gym_id == gym.id)
               .order_by(Payout.period_year.desc(), Payout.period_month.desc()).all())
    payments = (db.query(Payment)
                .filter(Payment.gym_id == gym.id,
                        Payment.status == PaymentStatus.success)
                .order_by(Payment.completed_at.desc()).limit(50).all())

    total_share = sum(p.gym_share or 0 for p in
                      db.query(Payment).filter(Payment.gym_id == gym.id,
                                               Payment.status == PaymentStatus.success).all())
    paid = sum(p.net_payable or 0 for p in payouts if p.status is PayoutStatus.paid)

    return {
        "gym": {"gym_code": gym.gym_code, "name": gym.name},
        "commission_percent": gym.commission_percent,
        "totals": {
            "lifetime_gym_share": int(total_share),
            "paid_out": int(paid),
            "awaiting_payout": int(total_share - paid),
        },
        "bank": {
            "account_name": owner.bank_account_name,
            "account_number": (f"****{owner.bank_account_number[-4:]}"
                               if owner.bank_account_number else None),
            "ifsc": owner.bank_ifsc, "upi_id": owner.upi_id,
            "configured": bool(owner.bank_account_number or owner.upi_id),
        },
        "payouts": [{
            "payout_ref": p.payout_ref,
            "period": f"{p.period_year}-{p.period_month:02d}",
            "gross_collected": p.gross_collected,
            "platform_commission": p.platform_commission,
            "net_payable": p.net_payable,
            "payment_count": p.payment_count,
            "status": p.status.value,
            "paid_at": p.paid_at.isoformat() if p.paid_at else None,
            "transfer_ref": p.transfer_ref,
        } for p in payouts],
        "recent_payments": [{
            "payment_ref": p.payment_ref, "amount": p.amount,
            "your_share": p.gym_share, "platform_fee": p.platform_commission,
            "completed_at": p.completed_at.isoformat() if p.completed_at else None,
            "settled": p.payout_id is not None,
        } for p in payments],
        "note": ("Members pay Fitora directly. Your share is transferred to your "
                 "registered bank account by the admin each month."),
    }
