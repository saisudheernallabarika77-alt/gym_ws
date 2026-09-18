"""
Fitora - SQLAlchemy ORM models

Covers all three portals:
  * User portal       -> User, Membership, Payment, EntryPass, DietPlan, Review
  * Gym owner portal  -> GymOwner, Gym, GymPlan, Coach, Equipment, Facility, GymImage
  * Admin portal      -> Admin, Payout, Complaint, AuditLog, OTPToken

Money rule (per spec): members always pay the PLATFORM. The admin later
settles each gym via a Payout row. No money moves gym-ward without a Payout.
"""
from __future__ import annotations
import enum
from datetime import datetime, date

from sqlalchemy import (
    Boolean, Column, Date, DateTime, Enum, Float, ForeignKey, Integer,
    JSON, String, Text, UniqueConstraint, Index,
)
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


def _now() -> datetime:
    return datetime.utcnow()


# --------------------------------------------------------------------- enums
class UserStatus(str, enum.Enum):
    pending_verification = "pending_verification"
    active = "active"
    blocked = "blocked"
    deleted = "deleted"


class GymStatus(str, enum.Enum):
    draft = "draft"                 # owner still filling the profile
    pending_approval = "pending_approval"
    active = "active"               # visible to users, indexed in RAG
    suspended = "suspended"
    rejected = "rejected"


class MembershipStatus(str, enum.Enum):
    pending_payment = "pending_payment"
    active = "active"
    due = "due"                     # renewal date passed, inside grace period
    overdue = "overdue"             # grace period expired -> shows in Dues
    expired = "expired"
    cancelled = "cancelled"
    removed = "removed"             # admin removed the member


class PaymentStatus(str, enum.Enum):
    initiated = "initiated"
    pending = "pending"
    success = "success"
    failed = "failed"
    refunded = "refunded"


class PayoutStatus(str, enum.Enum):
    scheduled = "scheduled"
    processing = "processing"
    paid = "paid"
    on_hold = "on_hold"
    failed = "failed"


class FitnessGoal(str, enum.Enum):
    weight_loss = "weight_loss"
    muscle_gain = "muscle_gain"
    strength = "strength"
    general_fitness = "general_fitness"
    endurance = "endurance"
    rehabilitation = "rehabilitation"


class OTPPurpose(str, enum.Enum):
    signup = "signup"
    login = "login"
    password_reset = "password_reset"
    gym_owner_signup = "gym_owner_signup"


# ---------------------------------------------------------------- user side
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    full_name = Column(String(120), nullable=False)
    email = Column(String(180), unique=True, nullable=False, index=True)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)

    # address / location captured at signup
    address = Column(Text)
    locality = Column(String(120))
    district = Column(String(120))
    state = Column(String(80), default="Andhra Pradesh")
    pincode = Column(String(10))
    latitude = Column(Float)
    longitude = Column(Float)

    # profile details reused to auto-fill the join form
    date_of_birth = Column(Date)
    gender = Column(String(20))
    height_cm = Column(Float)
    weight_kg = Column(Float)
    fitness_goal = Column(Enum(FitnessGoal))
    medical_notes = Column(Text)
    emergency_contact_name = Column(String(120))
    emergency_contact_phone = Column(String(20))
    photo_url = Column(String(300))

    status = Column(Enum(UserStatus), default=UserStatus.pending_verification, nullable=False)
    email_verified = Column(Boolean, default=False)
    blocked_reason = Column(Text)

    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)
    last_login_at = Column(DateTime)

    memberships = relationship("Membership", back_populates="user", cascade="all, delete-orphan")
    payments = relationship("Payment", back_populates="user")
    reviews = relationship("Review", back_populates="user")


class OTPToken(Base):
    __tablename__ = "otp_tokens"

    id = Column(Integer, primary_key=True)
    email = Column(String(180), nullable=False, index=True)
    code_hash = Column(String(255), nullable=False)
    purpose = Column(Enum(OTPPurpose), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    consumed_at = Column(DateTime)
    attempts = Column(Integer, default=0)
    created_at = Column(DateTime, default=_now)

    __table_args__ = (Index("ix_otp_email_purpose", "email", "purpose"),)


# ----------------------------------------------------------- gym owner side
class GymOwner(Base):
    __tablename__ = "gym_owners"

    id = Column(Integer, primary_key=True)
    full_name = Column(String(120), nullable=False)
    email = Column(String(180), unique=True, nullable=False, index=True)
    phone = Column(String(20), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)

    business_name = Column(String(180))
    # payout destination - admin settles here monthly
    bank_account_name = Column(String(150))
    bank_account_number = Column(String(40))
    bank_ifsc = Column(String(20))
    upi_id = Column(String(120))

    email_verified = Column(Boolean, default=False)
    status = Column(Enum(UserStatus), default=UserStatus.pending_verification, nullable=False)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    gyms = relationship("Gym", back_populates="owner", cascade="all, delete-orphan")


class Gym(Base):
    __tablename__ = "gyms"

    id = Column(Integer, primary_key=True)
    gym_code = Column(String(20), unique=True, nullable=False, index=True)  # FIT0001
    owner_id = Column(Integer, ForeignKey("gym_owners.id", ondelete="CASCADE"), index=True)

    name = Column(String(180), nullable=False)
    slug = Column(String(200), unique=True, index=True)
    description = Column(Text)
    tier = Column(String(20))                  # premium / standard / budget / ladies
    gym_type = Column(String(30), default="Unisex")

    # location
    address_line = Column(Text)
    locality = Column(String(120), index=True)
    district = Column(String(120), index=True)
    state = Column(String(80), default="Andhra Pradesh")
    pincode = Column(String(10))
    latitude = Column(Float, index=True)
    longitude = Column(Float, index=True)
    google_maps_url = Column(String(400))

    # contact
    phone = Column(String(20))
    alt_phone = Column(String(20))
    email = Column(String(180))
    website = Column(String(250))
    instagram = Column(String(120))

    # timings
    morning_open = Column(String(8))
    morning_close = Column(String(8))
    evening_open = Column(String(8))
    evening_close = Column(String(8))
    open_days = Column(String(60))
    weekly_off = Column(String(30))
    ladies_timing = Column(String(40))

    # pricing headline (plans live in GymPlan)
    monthly_fee = Column(Integer, nullable=False, default=0)
    registration_fee = Column(Integer, default=0)
    coach_included = Column(Boolean, default=False, nullable=False)
    coach_fee_separate = Column(Integer, default=0)
    trial_available = Column(Boolean, default=False)
    trial_days = Column(Integer, default=0)

    # amenities
    is_air_conditioned = Column(Boolean, default=False)
    supplements_available = Column(Boolean, default=False)
    facilities = Column(JSON, default=list)

    # media
    cover_image = Column(String(300))
    gallery = Column(JSON, default=list)

    # social proof
    rating = Column(Float, default=0.0)
    review_count = Column(Integer, default=0)
    member_count = Column(Integer, default=0)
    established_year = Column(Integer)

    # platform
    status = Column(Enum(GymStatus), default=GymStatus.draft, nullable=False, index=True)
    verified = Column(Boolean, default=False)
    data_source = Column(String(40), default="owner_submitted")
    indexed_in_rag = Column(Boolean, default=False)
    commission_percent = Column(Float, default=10.0)   # platform cut on each payment
    created_by_admin = Column(Boolean, default=False)  # admin-entered gyms
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    owner = relationship("GymOwner", back_populates="gyms")
    plans = relationship("GymPlan", back_populates="gym", cascade="all, delete-orphan")
    coaches = relationship("Coach", back_populates="gym", cascade="all, delete-orphan")
    equipment = relationship("Equipment", back_populates="gym", cascade="all, delete-orphan")
    memberships = relationship("Membership", back_populates="gym")
    reviews = relationship("Review", back_populates="gym")


class GymPlan(Base):
    __tablename__ = "gym_plans"

    id = Column(Integer, primary_key=True)
    gym_id = Column(Integer, ForeignKey("gyms.id", ondelete="CASCADE"), index=True)
    plan_name = Column(String(80), nullable=False)
    duration_months = Column(Integer, nullable=False)
    price = Column(Integer, nullable=False)
    effective_monthly = Column(Integer)
    savings = Column(Integer, default=0)
    coach_included = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)

    gym = relationship("Gym", back_populates="plans")


class Coach(Base):
    __tablename__ = "coaches"

    id = Column(Integer, primary_key=True)
    gym_id = Column(Integer, ForeignKey("gyms.id", ondelete="CASCADE"), index=True)
    name = Column(String(120), nullable=False)
    gender = Column(String(20))
    experience_years = Column(Integer, default=0)
    specialisations = Column(JSON, default=list)
    certifications = Column(JSON, default=list)
    bio = Column(Text)
    photo_url = Column(String(300))
    rating = Column(Float, default=0.0)
    is_active = Column(Boolean, default=True)

    gym = relationship("Gym", back_populates="coaches")


class Equipment(Base):
    __tablename__ = "equipment"

    id = Column(Integer, primary_key=True)
    gym_id = Column(Integer, ForeignKey("gyms.id", ondelete="CASCADE"), index=True)
    name = Column(String(150), nullable=False)
    category = Column(String(60))
    quantity = Column(Integer, default=1)
    description = Column(Text)
    image_url = Column(String(300))          # the owner's ACTUAL photo
    condition = Column(String(30), default="Good")
    is_active = Column(Boolean, default=True)

    gym = relationship("Gym", back_populates="equipment")


# -------------------------------------------------------- membership & money
class Membership(Base):
    __tablename__ = "memberships"

    id = Column(Integer, primary_key=True)
    membership_code = Column(String(24), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    gym_id = Column(Integer, ForeignKey("gyms.id", ondelete="CASCADE"), index=True)
    plan_id = Column(Integer, ForeignKey("gym_plans.id"))

    # snapshot of the join form
    goal = Column(Enum(FitnessGoal))
    weight_kg = Column(Float)
    height_cm = Column(Float)
    target_weight_kg = Column(Float)
    medical_notes = Column(Text)
    with_coach = Column(Boolean, default=False)
    assigned_coach_id = Column(Integer, ForeignKey("coaches.id"))

    # money snapshot (plan prices can change later)
    base_fee = Column(Integer, nullable=False)
    coach_fee = Column(Integer, default=0)
    registration_fee = Column(Integer, default=0)
    total_amount = Column(Integer, nullable=False)
    duration_months = Column(Integer, default=1)

    start_date = Column(Date)
    end_date = Column(Date, index=True)
    next_due_date = Column(Date, index=True)
    grace_days = Column(Integer, default=7)
    warning_sent_at = Column(DateTime)

    status = Column(Enum(MembershipStatus), default=MembershipStatus.pending_payment,
                    nullable=False, index=True)
    removed_reason = Column(Text)
    created_at = Column(DateTime, default=_now)
    updated_at = Column(DateTime, default=_now, onupdate=_now)

    user = relationship("User", back_populates="memberships")
    gym = relationship("Gym", back_populates="memberships")
    payments = relationship("Payment", back_populates="membership")
    entry_pass = relationship("EntryPass", back_populates="membership",
                              uselist=False, cascade="all, delete-orphan")
    diet_plan = relationship("DietPlan", back_populates="membership",
                             uselist=False, cascade="all, delete-orphan")

    __table_args__ = (UniqueConstraint("user_id", "gym_id", "start_date",
                                       name="uq_member_gym_start"),)


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
    payment_ref = Column(String(40), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), index=True)
    membership_id = Column(Integer, ForeignKey("memberships.id"), index=True)
    gym_id = Column(Integer, ForeignKey("gyms.id"), index=True)

    amount = Column(Integer, nullable=False)
    platform_commission = Column(Integer, default=0)
    gym_share = Column(Integer, default=0)       # what the payout owes the gym

    method = Column(String(30), default="UPI")
    upi_id = Column(String(120))
    gateway = Column(String(30), default="mock")
    gateway_txn_id = Column(String(80))
    status = Column(Enum(PaymentStatus), default=PaymentStatus.initiated,
                    nullable=False, index=True)
    failure_reason = Column(Text)

    payout_id = Column(Integer, ForeignKey("payouts.id"), index=True)

    created_at = Column(DateTime, default=_now)
    completed_at = Column(DateTime)

    user = relationship("User", back_populates="payments")
    membership = relationship("Membership", back_populates="payments")
    payout = relationship("Payout", back_populates="payments")


class Payout(Base):
    """Admin -> gym owner monthly settlement. The only path money reaches a gym."""
    __tablename__ = "payouts"

    id = Column(Integer, primary_key=True)
    payout_ref = Column(String(40), unique=True, nullable=False, index=True)
    gym_id = Column(Integer, ForeignKey("gyms.id"), index=True)
    owner_id = Column(Integer, ForeignKey("gym_owners.id"), index=True)

    period_month = Column(Integer, nullable=False)      # 1-12
    period_year = Column(Integer, nullable=False)
    gross_collected = Column(Integer, default=0)
    platform_commission = Column(Integer, default=0)
    net_payable = Column(Integer, default=0)
    payment_count = Column(Integer, default=0)

    status = Column(Enum(PayoutStatus), default=PayoutStatus.scheduled,
                    nullable=False, index=True)
    transfer_ref = Column(String(80))
    notes = Column(Text)
    scheduled_for = Column(Date)
    paid_at = Column(DateTime)
    processed_by_admin_id = Column(Integer, ForeignKey("admins.id"))
    created_at = Column(DateTime, default=_now)

    payments = relationship("Payment", back_populates="payout")

    __table_args__ = (UniqueConstraint("gym_id", "period_month", "period_year",
                                       name="uq_payout_gym_period"),)


# ------------------------------------------------------- pass, diet, reviews
class EntryPass(Base):
    __tablename__ = "entry_passes"

    id = Column(Integer, primary_key=True)
    pass_code = Column(String(32), unique=True, nullable=False, index=True)
    membership_id = Column(Integer, ForeignKey("memberships.id", ondelete="CASCADE"),
                           unique=True, index=True)

    qr_payload = Column(Text, nullable=False)   # signed token the gym scans
    qr_image_url = Column(String(300))
    photo_url = Column(String(300))

    valid_from = Column(Date)
    valid_until = Column(Date, index=True)
    is_active = Column(Boolean, default=True)
    scan_count = Column(Integer, default=0)
    last_scanned_at = Column(DateTime)

    created_at = Column(DateTime, default=_now)
    membership = relationship("Membership", back_populates="entry_pass")


class DietPlan(Base):
    __tablename__ = "diet_plans"

    id = Column(Integer, primary_key=True)
    membership_id = Column(Integer, ForeignKey("memberships.id", ondelete="CASCADE"),
                           unique=True, index=True)
    goal = Column(Enum(FitnessGoal), nullable=False)

    bmr = Column(Float)
    tdee = Column(Float)
    target_calories = Column(Integer)
    protein_g = Column(Integer)
    carbs_g = Column(Integer)
    fats_g = Column(Integer)
    water_litres = Column(Float)

    chart = Column(JSON, default=dict)     # meal-by-meal plan
    notes = Column(Text)
    created_at = Column(DateTime, default=_now)

    membership = relationship("Membership", back_populates="diet_plan")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True)
    gym_id = Column(Integer, ForeignKey("gyms.id", ondelete="CASCADE"), index=True)
    rating = Column(Integer, nullable=False)     # 1-5
    title = Column(String(150))
    comment = Column(Text)
    is_hidden = Column(Boolean, default=False)   # admin moderation
    created_at = Column(DateTime, default=_now)

    user = relationship("User", back_populates="reviews")
    gym = relationship("Gym", back_populates="reviews")

    __table_args__ = (UniqueConstraint("user_id", "gym_id", name="uq_review_user_gym"),)


# -------------------------------------------------------------- admin side
class Admin(Base):
    __tablename__ = "admins"

    id = Column(Integer, primary_key=True)
    full_name = Column(String(120), nullable=False)
    email = Column(String(180), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(30), default="admin")     # admin / superadmin
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=_now)
    last_login_at = Column(DateTime)


class Complaint(Base):
    """
    Two directions into the same table, both -> admin only (admin is the sole
    decision-maker in either direction):
      * Gym owner -> admin, about a member (raised_by_owner_id set,
        against_user_id set) - e.g. a payment default.
      * Member -> admin, about a gym (raised_by_user_id set, gym_id set) -
        e.g. a service complaint, fraud, or safety issue.
    Exactly one of raised_by_owner_id / raised_by_user_id is set per row.
    """
    __tablename__ = "complaints"

    id = Column(Integer, primary_key=True)
    gym_id = Column(Integer, ForeignKey("gyms.id"), index=True)
    raised_by_owner_id = Column(Integer, ForeignKey("gym_owners.id"), index=True)
    raised_by_user_id = Column(Integer, ForeignKey("users.id"), index=True)
    against_user_id = Column(Integer, ForeignKey("users.id"), index=True)
    membership_id = Column(Integer, ForeignKey("memberships.id"))

    # payment_default / misconduct / damage / other (owner->admin)
    # service_issue / fraud / safety / billing / other (user->admin)
    category = Column(String(60))
    subject = Column(String(200), nullable=False)
    details = Column(Text)
    status = Column(String(30), default="open")   # open / reviewing / resolved / dismissed
    admin_action = Column(Text)
    resolved_by_admin_id = Column(Integer, ForeignKey("admins.id"))
    created_at = Column(DateTime, default=_now)
    resolved_at = Column(DateTime)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    actor_type = Column(String(20))       # admin / gym_owner / user / system
    actor_id = Column(Integer)
    action = Column(String(80), nullable=False, index=True)
    entity_type = Column(String(40))
    entity_id = Column(String(40))
    details = Column(JSON, default=dict)
    ip_address = Column(String(45))
    created_at = Column(DateTime, default=_now, index=True)
