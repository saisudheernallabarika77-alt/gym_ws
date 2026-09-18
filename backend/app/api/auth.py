"""
Fitora - Authentication for all three portals.

User / gym-owner signup flow (per spec):
    POST /signup          -> create pending account, email a 6-digit OTP
    POST /verify-otp      -> consume OTP, activate account, redirect to login
    POST /login           -> email + password -> JWT

Admins are seeded, not self-registered.
"""
from __future__ import annotations
from datetime import datetime, timedelta

from fastapi import APIRouter, HTTPException, Request, status
from sqlalchemy import func

from ..core.config import settings
from ..core.ratelimit import rate_limit_login, rate_limit_otp_request
from ..core.security import (
    create_access_token, generate_otp, hash_otp, hash_password,
    verify_otp, verify_password,
)
from ..db.models import (
    Admin, AuditLog, GymOwner, OTPPurpose, OTPToken, User, UserStatus,
)
from ..schemas.auth import (
    LoginRequest, MessageResponse, OTPResendRequest, OTPVerifyRequest,
    OwnerSignupRequest, TokenResponse, UserSignupRequest,
)
from ..services.email_service import send_otp_email, send_welcome_email
from .deps import CurrentUser, DbSession

router = APIRouter(prefix="/auth", tags=["auth"])


# ----------------------------------------------------------------- helpers
def _issue_otp(db, email: str, purpose: OTPPurpose) -> str:
    """Invalidate any live OTP for this email+purpose, then mint a fresh one."""
    (db.query(OTPToken)
       .filter(OTPToken.email == email,
               OTPToken.purpose == purpose,
               OTPToken.consumed_at.is_(None))
       .update({"consumed_at": datetime.utcnow()}))

    code = generate_otp()
    db.add(OTPToken(
        email=email,
        code_hash=hash_otp(code),
        purpose=purpose,
        expires_at=datetime.utcnow() + timedelta(minutes=settings.OTP_TTL_MINUTES),
    ))
    db.commit()
    send_otp_email(email, code, purpose.value)
    return code


def _consume_otp(db, email: str, code: str, purpose: OTPPurpose) -> None:
    token = (db.query(OTPToken)
             .filter(OTPToken.email == email,
                     OTPToken.purpose == purpose,
                     OTPToken.consumed_at.is_(None))
             .order_by(OTPToken.created_at.desc())
             .first())

    if token is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "No verification code pending. Request a new one.")
    if token.expires_at < datetime.utcnow():
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            "This code has expired. Request a new one.")
    if token.attempts >= settings.OTP_MAX_ATTEMPTS:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            "Too many wrong attempts. Request a new code.")

    if not verify_otp(code.strip(), token.code_hash):
        token.attempts += 1
        db.commit()
        left = settings.OTP_MAX_ATTEMPTS - token.attempts
        raise HTTPException(status.HTTP_400_BAD_REQUEST,
                            f"Incorrect code. {left} attempt(s) left.")

    token.consumed_at = datetime.utcnow()
    db.commit()


def _user_profile(u: User) -> dict:
    return {
        "id": u.id, "full_name": u.full_name, "email": u.email, "phone": u.phone,
        "address": u.address, "locality": u.locality, "district": u.district,
        "pincode": u.pincode, "latitude": u.latitude, "longitude": u.longitude,
        "date_of_birth": u.date_of_birth.isoformat() if u.date_of_birth else None,
        "gender": u.gender, "height_cm": u.height_cm, "weight_kg": u.weight_kg,
        "fitness_goal": u.fitness_goal.value if u.fitness_goal else None,
        "medical_notes": u.medical_notes,
        "emergency_contact_name": u.emergency_contact_name,
        "emergency_contact_phone": u.emergency_contact_phone,
        "photo_url": u.photo_url, "status": u.status.value,
        "email_verified": u.email_verified,
    }


# ------------------------------------------------------------ user signup
@router.post("/signup", response_model=MessageResponse,
             status_code=status.HTTP_201_CREATED)
def signup(payload: UserSignupRequest, request: Request, db: DbSession):
    email = payload.email.lower().strip()
    rate_limit_otp_request(request, email)

    existing = db.query(User).filter(func.lower(User.email) == email).first()
    if existing:
        if existing.email_verified:
            raise HTTPException(status.HTTP_409_CONFLICT,
                                "An account with this email already exists. Please log in.")
        # unverified signup being retried - refresh details and re-send the code
        existing.full_name = payload.full_name
        existing.phone = payload.phone
        existing.password_hash = hash_password(payload.password)
        existing.address = payload.address
        existing.locality = payload.locality
        existing.district = payload.district
        existing.pincode = payload.pincode
        existing.latitude = payload.latitude
        existing.longitude = payload.longitude
        db.commit()
        _issue_otp(db, email, OTPPurpose.signup)
        return MessageResponse(
            message=f"Verification code sent to {email}.",
            data={"email": email, "next": "verify-otp",
                  "expires_in_minutes": settings.OTP_TTL_MINUTES},
        )

    if db.query(User).filter(User.phone == payload.phone).first():
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "This phone number is already registered.")

    user = User(
        full_name=payload.full_name.strip(),
        email=email,
        phone=payload.phone,
        password_hash=hash_password(payload.password),
        address=payload.address,
        locality=payload.locality,
        district=payload.district,
        pincode=payload.pincode,
        latitude=payload.latitude,
        longitude=payload.longitude,
        status=UserStatus.pending_verification,
    )
    db.add(user)
    db.commit()

    _issue_otp(db, email, OTPPurpose.signup)
    return MessageResponse(
        message=f"Verification code sent to {email}.",
        data={"email": email, "next": "verify-otp",
              "expires_in_minutes": settings.OTP_TTL_MINUTES},
    )


@router.post("/verify-otp", response_model=MessageResponse)
def verify_signup_otp(payload: OTPVerifyRequest, db: DbSession):
    email = payload.email.lower().strip()
    user = db.query(User).filter(func.lower(User.email) == email).first()
    if not user:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No signup found for this email.")
    if user.email_verified:
        return MessageResponse(message="Already verified. Please log in.",
                               data={"next": "login"})

    _consume_otp(db, email, payload.code, OTPPurpose.signup)

    user.email_verified = True
    user.status = UserStatus.active
    db.add(AuditLog(actor_type="user", actor_id=user.id, action="signup_verified",
                    entity_type="user", entity_id=str(user.id)))
    db.commit()

    send_welcome_email(user.email, user.full_name)
    return MessageResponse(
        message="Email verified. You can now log in.",
        data={"next": "login", "email": email},
    )


@router.post("/resend-otp", response_model=MessageResponse)
def resend_otp(payload: OTPResendRequest, request: Request, db: DbSession):
    email = payload.email.lower().strip()
    rate_limit_otp_request(request, email)
    try:
        purpose = OTPPurpose(payload.purpose)
    except ValueError:
        purpose = OTPPurpose.signup

    recent = (db.query(OTPToken)
              .filter(OTPToken.email == email, OTPToken.purpose == purpose)
              .order_by(OTPToken.created_at.desc()).first())
    if recent and (datetime.utcnow() - recent.created_at).total_seconds() < 30:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            "Please wait 30 seconds before requesting another code.")

    _issue_otp(db, email, purpose)
    return MessageResponse(
        message=f"New code sent to {email}.",
        data={"expires_in_minutes": settings.OTP_TTL_MINUTES},
    )


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request, db: DbSession):
    email = payload.email.lower().strip()
    rate_limit_login(request, email)
    user = db.query(User).filter(func.lower(User.email) == email).first()

    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
    if not user.email_verified:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "Email not verified. Check your inbox for the code.")
    if user.status is UserStatus.blocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            f"Account blocked. {user.blocked_reason or 'Contact support.'}")
    if user.status is UserStatus.deleted:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account no longer exists.")

    user.last_login_at = datetime.utcnow()
    db.commit()

    return TokenResponse(
        access_token=create_access_token(user.id, "user", {"email": user.email}),
        role="user",
        expires_in_minutes=settings.ACCESS_TOKEN_MINUTES,
        profile=_user_profile(user),
    )


@router.get("/me")
def me(user: CurrentUser):
    return _user_profile(user)


# ----------------------------------------------------------- owner signup
@router.post("/owner/signup", response_model=MessageResponse,
             status_code=status.HTTP_201_CREATED)
def owner_signup(payload: OwnerSignupRequest, request: Request, db: DbSession):
    email = payload.email.lower().strip()
    rate_limit_otp_request(request, email)

    existing = db.query(GymOwner).filter(func.lower(GymOwner.email) == email).first()
    if existing and existing.email_verified:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "A partner account with this email already exists.")

    if existing:
        existing.full_name = payload.full_name
        existing.phone = payload.phone
        existing.business_name = payload.business_name
        existing.password_hash = hash_password(payload.password)
    else:
        db.add(GymOwner(
            full_name=payload.full_name.strip(),
            email=email,
            phone=payload.phone,
            business_name=payload.business_name.strip(),
            password_hash=hash_password(payload.password),
            status=UserStatus.pending_verification,
        ))
    db.commit()

    _issue_otp(db, email, OTPPurpose.gym_owner_signup)
    return MessageResponse(
        message=f"Verification code sent to {email}.",
        data={"email": email, "next": "verify-otp",
              "expires_in_minutes": settings.OTP_TTL_MINUTES},
    )


@router.post("/owner/verify-otp", response_model=MessageResponse)
def owner_verify(payload: OTPVerifyRequest, db: DbSession):
    email = payload.email.lower().strip()
    owner = db.query(GymOwner).filter(func.lower(GymOwner.email) == email).first()
    if not owner:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No partner signup found.")
    if owner.email_verified:
        return MessageResponse(message="Already verified. Please log in.",
                               data={"next": "login"})

    _consume_otp(db, email, payload.code, OTPPurpose.gym_owner_signup)
    owner.email_verified = True
    owner.status = UserStatus.active
    db.commit()

    return MessageResponse(
        message="Partner account verified. Log in to set up your gym.",
        data={"next": "login", "email": email},
    )


@router.post("/owner/login", response_model=TokenResponse)
def owner_login(payload: LoginRequest, request: Request, db: DbSession):
    from ..db.models import Gym

    email = payload.email.lower().strip()
    rate_limit_login(request, email)
    owner = db.query(GymOwner).filter(func.lower(GymOwner.email) == email).first()

    if not owner or not verify_password(payload.password, owner.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
    if not owner.email_verified:
        raise HTTPException(status.HTTP_403_FORBIDDEN,
                            "Email not verified. Check your inbox for the code.")
    if owner.status is UserStatus.blocked:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Partner account suspended.")

    gyms = db.query(Gym).filter(Gym.owner_id == owner.id).all()
    return TokenResponse(
        access_token=create_access_token(owner.id, "gym_owner", {"email": owner.email}),
        role="gym_owner",
        expires_in_minutes=settings.ACCESS_TOKEN_MINUTES,
        profile={
            "id": owner.id, "full_name": owner.full_name, "email": owner.email,
            "phone": owner.phone, "business_name": owner.business_name,
            "upi_id": owner.upi_id,
            "bank_account_number": owner.bank_account_number,
            "bank_ifsc": owner.bank_ifsc,
            "gym_count": len(gyms),
            # the owner portal uses this to decide onboarding vs dashboard
            "needs_onboarding": len(gyms) == 0 or all(
                g.status.value == "draft" for g in gyms),
            "gyms": [{"id": g.id, "gym_code": g.gym_code, "name": g.name,
                      "status": g.status.value} for g in gyms],
        },
    )


# ------------------------------------------------------------ admin login
@router.post("/admin/login", response_model=TokenResponse)
def admin_login(payload: LoginRequest, request: Request, db: DbSession):
    email = payload.email.lower().strip()
    # Admin login gets the tightest limit - there are only a handful of
    # legitimate admin accounts, so any volume here is almost certainly an attack.
    rate_limit_login(request, email)
    admin = db.query(Admin).filter(func.lower(Admin.email) == email).first()

    if not admin or not verify_password(payload.password, admin.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect email or password.")
    if not admin.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Admin account disabled.")

    admin.last_login_at = datetime.utcnow()
    db.add(AuditLog(actor_type="admin", actor_id=admin.id, action="admin_login",
                    entity_type="admin", entity_id=str(admin.id)))
    db.commit()

    return TokenResponse(
        access_token=create_access_token(admin.id, admin.role, {"email": admin.email}),
        role=admin.role,
        expires_in_minutes=settings.ACCESS_TOKEN_MINUTES,
        profile={"id": admin.id, "full_name": admin.full_name,
                 "email": admin.email, "role": admin.role},
    )
