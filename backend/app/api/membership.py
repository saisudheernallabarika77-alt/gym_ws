"""
Fitora - Join a gym, pay, and get the digital entry pass.

The exact flow from the spec:
    GET  /join/{gym_code}/prefill   -> form pre-filled from the saved profile
    POST /join/{gym_code}           -> membership created, payment order returned
    POST /pay/{payment_ref}         -> UPI confirmation -> membership activated
    GET  /pass/{membership_code}    -> the card: photo + QR + details
    GET  /diet/{membership_code}    -> the diet chart that ships with the pass
"""
from __future__ import annotations
from datetime import date, datetime, timedelta
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..core.config import settings
from ..core.ratelimit import rate_limit_scan
from ..core.security import generate_code
from ..db.models import (
    AuditLog, Coach, DietPlan, EntryPass, Gym, GymPlan, GymStatus,
    Membership, MembershipStatus, Payment, PaymentStatus, FitnessGoal, User,
)
from ..services.diet_service import build_diet_chart, GOAL_LABEL
from ..services.email_service import send_membership_confirmation
from ..services.pass_service import build_pass_view, build_qr_payload, new_pass_code
from ..services.payment_service import get_gateway, new_payment_ref, split_amount
from .deps import CurrentUser, DbSession

router = APIRouter(tags=["membership"])


class JoinRequest(BaseModel):
    plan_id: int
    with_coach: bool = False
    preferred_coach_id: int | None = None
    # the extra details the join form collects on top of the profile
    weight_kg: float = Field(ge=25, le=250)
    height_cm: float = Field(ge=80, le=250)
    target_weight_kg: float | None = Field(default=None, ge=25, le=250)
    goal: str
    activity_level: str = "moderate"
    medical_notes: str | None = None
    emergency_contact_name: str | None = None
    emergency_contact_phone: str | None = None


class PayRequest(BaseModel):
    upi_id: str | None = None
    gateway_payload: dict = Field(default_factory=dict)


def _goal_enum(value: str) -> FitnessGoal:
    try:
        return FitnessGoal(value)
    except ValueError:
        return FitnessGoal.general_fitness


def _age_of(user) -> int:
    if not user.date_of_birth:
        return 25
    today = date.today()
    return today.year - user.date_of_birth.year - (
        (today.month, today.day) < (user.date_of_birth.month, user.date_of_birth.day)
    )


# --------------------------------------------------------------- prefill
@router.get("/join/{gym_code}/prefill")
def join_prefill(gym_code: str, db: DbSession, user: CurrentUser):
    gym = db.query(Gym).filter(Gym.gym_code == gym_code.upper()).first()
    if not gym or gym.status is not GymStatus.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Gym not found")

    live = (db.query(Membership)
            .filter(Membership.user_id == user.id, Membership.gym_id == gym.id,
                    Membership.status.in_([MembershipStatus.active,
                                           MembershipStatus.due,
                                           MembershipStatus.overdue]))
            .first())

    plans = (db.query(GymPlan)
             .filter(GymPlan.gym_id == gym.id, GymPlan.is_active.is_(True))
             .order_by(GymPlan.duration_months).all())
    coaches = (db.query(Coach)
               .filter(Coach.gym_id == gym.id, Coach.is_active.is_(True))
               .order_by(Coach.experience_years.desc()).all())

    return {
        "gym": {
            "gym_code": gym.gym_code, "name": gym.name, "locality": gym.locality,
            "cover_image": gym.cover_image, "phone": gym.phone,
            "monthly_fee": gym.monthly_fee,
            "registration_fee": gym.registration_fee,
            "coach_included": gym.coach_included,
            "coach_fee_separate": gym.coach_fee_separate,
            "coach_fee_note": (
                "Coach is included in the membership fee." if gym.coach_included
                else f"Personal coach costs Rs.{gym.coach_fee_separate}/month extra."
            ),
        },
        # auto-filled from the profile, exactly as the spec asks
        "prefill": {
            "full_name": user.full_name, "email": user.email, "phone": user.phone,
            "address": user.address, "locality": user.locality,
            "district": user.district, "pincode": user.pincode,
            "date_of_birth": user.date_of_birth.isoformat() if user.date_of_birth else None,
            "age": _age_of(user), "gender": user.gender,
            "height_cm": user.height_cm, "weight_kg": user.weight_kg,
            "goal": user.fitness_goal.value if user.fitness_goal else None,
            "medical_notes": user.medical_notes,
            "emergency_contact_name": user.emergency_contact_name,
            "emergency_contact_phone": user.emergency_contact_phone,
            "photo_url": user.photo_url,
        },
        "plans": [{
            "id": p.id, "plan_name": p.plan_name, "duration_months": p.duration_months,
            "price": p.price, "effective_monthly": p.effective_monthly,
            "savings": p.savings, "coach_included": p.coach_included,
        } for p in plans],
        "coaches": [{
            "id": c.id, "name": c.name, "gender": c.gender,
            "experience_years": c.experience_years,
            "specialisations": c.specialisations or [], "photo_url": c.photo_url,
            "rating": c.rating,
        } for c in coaches],
        "goals": [{"value": g.value, "label": GOAL_LABEL.get(g.value, g.value)}
                  for g in FitnessGoal],
        "activity_levels": [
            {"value": "sedentary", "label": "Sedentary (desk job, no exercise)"},
            {"value": "light", "label": "Lightly active (1-3 days/week)"},
            {"value": "moderate", "label": "Moderately active (3-5 days/week)"},
            {"value": "active", "label": "Very active (6-7 days/week)"},
            {"value": "very_active", "label": "Athlete (twice daily)"},
        ],
        "already_member": live is not None,
        "existing_membership_code": live.membership_code if live else None,
    }


# ------------------------------------------------------------------ join
@router.post("/join/{gym_code}", status_code=status.HTTP_201_CREATED)
def join_gym(gym_code: str, payload: JoinRequest, db: DbSession, user: CurrentUser):
    gym = db.query(Gym).filter(Gym.gym_code == gym_code.upper()).first()
    if not gym or gym.status is not GymStatus.active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Gym not found")

    live = (db.query(Membership)
            .filter(Membership.user_id == user.id, Membership.gym_id == gym.id,
                    Membership.status.in_([MembershipStatus.active,
                                           MembershipStatus.due,
                                           MembershipStatus.overdue]))
            .first())
    if live:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            f"You already have an active membership here "
                            f"({live.membership_code}).")

    # An unpaid attempt from earlier today would collide with the
    # (user, gym, start_date) uniqueness rule, so reuse it instead: the user is
    # simply retrying checkout. Its old payment order is abandoned.
    pending = (db.query(Membership)
               .filter(Membership.user_id == user.id, Membership.gym_id == gym.id,
                       Membership.status == MembershipStatus.pending_payment,
                       Membership.start_date == date.today())
               .first())
    if pending:
        (db.query(Payment)
           .filter(Payment.membership_id == pending.id,
                   Payment.status.in_([PaymentStatus.initiated,
                                       PaymentStatus.pending]))
           .update({"status": PaymentStatus.failed,
                    "failure_reason": "Superseded by a new checkout"},
                   synchronize_session=False))
        db.delete(pending)
        db.flush()

    plan = db.get(GymPlan, payload.plan_id)
    if not plan or plan.gym_id != gym.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid plan for this gym.")

    with_coach = gym.coach_included or payload.with_coach or plan.coach_included
    coach_fee = 0
    if with_coach and not (gym.coach_included or plan.coach_included):
        coach_fee = gym.coach_fee_separate * plan.duration_months

    coach = None
    if with_coach:
        if payload.preferred_coach_id:
            coach = db.get(Coach, payload.preferred_coach_id)
            if coach and coach.gym_id != gym.id:
                coach = None
        if coach is None:
            coach = (db.query(Coach).filter(Coach.gym_id == gym.id,
                                            Coach.is_active.is_(True))
                     .order_by(Coach.experience_years.desc()).first())

    base_fee = plan.price
    reg_fee = gym.registration_fee
    total = base_fee + coach_fee + reg_fee

    start = date.today()
    end = start + timedelta(days=30 * plan.duration_months)

    ms = Membership(
        membership_code=generate_code("FTM", 9),
        user_id=user.id, gym_id=gym.id, plan_id=plan.id,
        goal=_goal_enum(payload.goal),
        weight_kg=payload.weight_kg, height_cm=payload.height_cm,
        target_weight_kg=payload.target_weight_kg,
        medical_notes=payload.medical_notes,
        with_coach=with_coach,
        assigned_coach_id=coach.id if coach else None,
        base_fee=base_fee, coach_fee=coach_fee, registration_fee=reg_fee,
        total_amount=total, duration_months=plan.duration_months,
        start_date=start, end_date=end, next_due_date=end,
        grace_days=settings.DEFAULT_GRACE_DAYS,
        status=MembershipStatus.pending_payment,
    )
    db.add(ms)

    # keep the profile current so the next join pre-fills correctly
    user.weight_kg = payload.weight_kg
    user.height_cm = payload.height_cm
    user.fitness_goal = _goal_enum(payload.goal)
    if payload.medical_notes:
        user.medical_notes = payload.medical_notes
    if payload.emergency_contact_name:
        user.emergency_contact_name = payload.emergency_contact_name
    if payload.emergency_contact_phone:
        user.emergency_contact_phone = payload.emergency_contact_phone
    db.flush()

    sp = split_amount(total, gym.commission_percent)
    ref = new_payment_ref()
    pay = Payment(
        payment_ref=ref, user_id=user.id, membership_id=ms.id, gym_id=gym.id,
        amount=total,
        platform_commission=sp["platform_commission"],
        gym_share=sp["gym_share"],
        method="UPI", gateway=settings.PAYMENT_GATEWAY,
        status=PaymentStatus.initiated,
    )
    db.add(pay)
    db.commit()

    order = get_gateway().create_order(
        amount=total, ref=ref,
        description=f"{gym.name} - {plan.plan_name}",
        customer={"name": user.full_name, "email": user.email, "phone": user.phone},
    )

    return {
        "membership_code": ms.membership_code,
        "status": ms.status.value,
        "gym": {"gym_code": gym.gym_code, "name": gym.name},
        "breakdown": {
            "plan": plan.plan_name,
            "duration_months": plan.duration_months,
            "base_fee": base_fee,
            "coach_fee": coach_fee,
            "coach_note": ("Coach included - no extra charge" if gym.coach_included
                           else (f"Personal coach for {plan.duration_months} month(s)"
                                 if coach_fee else "No personal coach selected")),
            "registration_fee": reg_fee,
            "total": total,
        },
        "assigned_coach": ({"id": coach.id, "name": coach.name,
                            "experience_years": coach.experience_years}
                           if coach else None),
        "payment": order,
        "next": "payment",
    }


# --------------------------------------------------------------- payment
def _activate_paid_membership(
    db, *, pay_row: Payment, ms: Membership, gym: Gym, user: User,
    gateway_txn_id: str, upi_id: str | None,
) -> dict:
    """
    The one place a Payment/Membership actually flips to success and gets
    its entry pass + diet chart issued. Called from the mock-gateway path in
    `pay()` directly (there's no real bank to call back to), and from the
    Razorpay webhook handler - never from anywhere that only has
    client-supplied data with no gateway-verified signature behind it.
    """
    pay_row.status = PaymentStatus.success
    pay_row.gateway_txn_id = gateway_txn_id
    pay_row.upi_id = upi_id
    pay_row.completed_at = datetime.utcnow()

    ms.status = MembershipStatus.active
    gym.member_count = (gym.member_count or 0) + 1

    pass_code = new_pass_code()
    qr_payload = build_qr_payload(
        pass_code=pass_code, membership_code=ms.membership_code,
        user_id=user.id, user_name=user.full_name,
        gym_code=gym.gym_code, gym_name=gym.name,
        goal=ms.goal.value if ms.goal else "general_fitness",
        plan_name=db.get(GymPlan, ms.plan_id).plan_name if ms.plan_id else "Membership",
        with_coach=ms.with_coach,
        valid_from=ms.start_date, valid_until=ms.end_date,
    )
    db.add(EntryPass(
        pass_code=pass_code, membership_id=ms.id, qr_payload=qr_payload,
        photo_url=user.photo_url, valid_from=ms.start_date,
        valid_until=ms.end_date, is_active=True,
    ))

    dc = build_diet_chart(
        weight_kg=ms.weight_kg or user.weight_kg or 70,
        height_cm=ms.height_cm or user.height_cm or 170,
        age=_age_of(user), gender=user.gender or "Male",
        goal=ms.goal.value if ms.goal else "general_fitness",
        target_weight_kg=ms.target_weight_kg,
    )
    db.add(DietPlan(
        membership_id=ms.id, goal=ms.goal or FitnessGoal.general_fitness,
        bmr=dc["bmr"], tdee=dc["tdee"], target_calories=dc["target_calories"],
        protein_g=dc["protein_g"], carbs_g=dc["carbs_g"], fats_g=dc["fats_g"],
        water_litres=dc["water_litres"], chart=dc["chart"],
        notes=f"{dc['goal_label']} plan. BMI {dc['bmi']} ({dc['bmi_band']}).",
    ))

    db.add(AuditLog(actor_type="user", actor_id=user.id, action="membership_paid",
                    entity_type="membership", entity_id=ms.membership_code,
                    details={"gym": gym.gym_code, "amount": pay_row.amount,
                             "gateway": pay_row.gateway}))
    db.commit()

    send_membership_confirmation(
        user.email, user.full_name, gym.name, pass_code,
        ms.end_date.strftime("%d %b %Y"), pay_row.amount,
    )

    return {
        "success": True,
        "message": "Payment successful. Your entry pass is ready.",
        "payment_ref": pay_row.payment_ref,
        "gateway_txn_id": pay_row.gateway_txn_id,
        "amount_paid": pay_row.amount,
        "membership_code": ms.membership_code,
        "pass_code": pass_code,
        "next": f"/pass/{ms.membership_code}",
    }


@router.post("/pay/{payment_ref}")
def pay(payment_ref: str, payload: PayRequest, db: DbSession, user: CurrentUser):
    """
    Confirms payment for the MOCK gateway, where there is no real bank to
    call this back, so the client-driven confirm() is the only signal there
    is - acceptable because nothing real is at stake.

    For Razorpay, this endpoint intentionally does NOT finalize the payment.
    It only records that checkout completed from the browser's point of
    view; the membership is activated exclusively by `razorpay_webhook()`
    below once Razorpay's servers confirm the charge server-to-server. This
    prevents a client from calling /pay/{ref} directly with a fabricated
    payload to grant itself a membership with no money having moved.
    """
    pay_row = db.query(Payment).filter(Payment.payment_ref == payment_ref).first()
    if not pay_row or pay_row.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Payment not found")
    if pay_row.status is PaymentStatus.success:
        raise HTTPException(status.HTTP_409_CONFLICT, "This payment is already complete.")

    ms = db.get(Membership, pay_row.membership_id)
    gym = db.get(Gym, pay_row.gym_id)
    if not ms or not gym:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Membership not found")

    result = get_gateway(pay_row.gateway).confirm(
        ref=payment_ref,
        gateway_payload={"upi_id": payload.upi_id, **payload.gateway_payload},
    )

    if result["status"] == "pending_webhook":
        # Razorpay: signature checked out, but activation waits for the
        # webhook. Record the intermediate state and tell the client to poll.
        pay_row.status = PaymentStatus.pending
        pay_row.gateway_txn_id = result.get("gateway_txn_id")
        db.commit()
        return {
            "success": True,
            "status": "pending_webhook",
            "message": "Payment received - confirming with the bank. This finalizes automatically.",
            "payment_ref": payment_ref,
        }

    if result["status"] != "success":
        pay_row.status = PaymentStatus.failed
        pay_row.failure_reason = result.get("reason")
        db.commit()
        raise HTTPException(status.HTTP_402_PAYMENT_REQUIRED,
                            result.get("reason", "Payment failed. Please try again."))

    return _activate_paid_membership(
        db, pay_row=pay_row, ms=ms, gym=gym, user=user,
        gateway_txn_id=result["gateway_txn_id"],
        upi_id=payload.upi_id or result.get("upi_id"),
    )


@router.post("/webhooks/razorpay", include_in_schema=False)
async def razorpay_webhook(request: Request, db: DbSession):
    """
    Server-to-server callback from Razorpay - the only path that finalizes a
    Razorpay payment. Verified against RAZORPAY_WEBHOOK_SECRET, a value only
    Razorpay's servers and this backend know; the browser/checkout client is
    never in this loop, so it cannot forge or replay a call to this route
    the way it could a client-invoked confirmation endpoint.

    Configure this URL (https://yourdomain/api/v1/webhooks/razorpay) under
    Razorpay Dashboard -> Settings -> Webhooks, subscribed to
    `payment.captured`, and put the webhook's own secret (not the API key
    secret) in RAZORPAY_WEBHOOK_SECRET.
    """
    from ..services.payment_service import verify_razorpay_webhook_signature

    body = await request.body()
    signature = request.headers.get("x-razorpay-signature", "")
    if not verify_razorpay_webhook_signature(body, signature):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid webhook signature")

    import json as _json
    event = _json.loads(body)
    if event.get("event") != "payment.captured":
        return {"ok": True, "ignored": event.get("event")}

    payment_entity = event.get("payload", {}).get("payment", {}).get("entity", {})
    ref = payment_entity.get("notes", {}).get("ref") or payment_entity.get("order_id")
    razorpay_payment_id = payment_entity.get("id")

    pay_row = db.query(Payment).filter(Payment.payment_ref == ref).first()
    if not pay_row:
        # Don't 4xx - Razorpay retries on non-2xx, and a ref we don't
        # recognise will never resolve on retry either.
        return {"ok": True, "warning": "no matching payment_ref"}
    if pay_row.status is PaymentStatus.success:
        return {"ok": True, "already_processed": True}   # webhook retry, not an error

    ms = db.get(Membership, pay_row.membership_id)
    gym = db.get(Gym, pay_row.gym_id)
    user = db.get(User, pay_row.user_id)
    if not (ms and gym and user):
        return {"ok": True, "warning": "membership/gym/user missing"}

    _activate_paid_membership(
        db, pay_row=pay_row, ms=ms, gym=gym, user=user,
        gateway_txn_id=razorpay_payment_id, upi_id=None,
    )
    return {"ok": True}


# ------------------------------------------------------------ entry pass
@router.get("/pass/{membership_code}")
def get_pass(membership_code: str, db: DbSession, user: CurrentUser):
    ms = (db.query(Membership)
          .filter(Membership.membership_code == membership_code.upper()).first())
    if not ms or ms.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Membership not found")

    ep = db.query(EntryPass).filter(EntryPass.membership_id == ms.id).first()
    if not ep:
        raise HTTPException(status.HTTP_404_NOT_FOUND,
                            "No pass issued yet - complete the payment first.")

    gym = db.get(Gym, ms.gym_id)
    plan = db.get(GymPlan, ms.plan_id) if ms.plan_id else None
    coach = db.get(Coach, ms.assigned_coach_id) if ms.assigned_coach_id else None

    view = build_pass_view(
        pass_code=ep.pass_code, qr_payload=ep.qr_payload,
        user_name=user.full_name, user_photo_url=ep.photo_url or user.photo_url,
        member_since=ms.start_date,
        gym_name=gym.name, gym_locality=gym.locality, gym_phone=gym.phone,
        plan_name=plan.plan_name if plan else "Membership",
        goal_label=GOAL_LABEL.get(ms.goal.value if ms.goal else "", "General Fitness"),
        with_coach=ms.with_coach, coach_name=coach.name if coach else None,
        valid_from=ms.start_date, valid_until=ms.end_date,
        amount_paid=ms.total_amount,
    )
    view["membership_code"] = ms.membership_code
    view["membership_status"] = ms.status.value
    view["pass_active"] = ep.is_active
    view["scan_count"] = ep.scan_count
    view["gym"]["gym_code"] = gym.gym_code
    view["gym"]["address"] = gym.address_line
    view["gym"]["maps_url"] = gym.google_maps_url
    view["gym"]["timings"] = (f"{gym.morning_open}-{gym.morning_close}, "
                              f"{gym.evening_open}-{gym.evening_close}")
    return view


def _load_diet(membership_code: str, db, user) -> dict[str, Any]:
    """Shared by the JSON view and the PDF download so both render identical data."""
    ms = (db.query(Membership)
          .filter(Membership.membership_code == membership_code.upper()).first())
    if not ms or ms.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Membership not found")

    dp = db.query(DietPlan).filter(DietPlan.membership_id == ms.id).first()
    if not dp:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No diet chart for this membership.")

    full = build_diet_chart(
        weight_kg=ms.weight_kg or 70, height_cm=ms.height_cm or 170,
        age=_age_of(user), gender=user.gender or "Male",
        goal=dp.goal.value, target_weight_kg=ms.target_weight_kg,
    )
    gym = db.get(Gym, ms.gym_id)
    return {
        "membership_code": ms.membership_code,
        "member_name": user.full_name,
        "gym_name": gym.name if gym else "",
        "goal": dp.goal.value,
        "goal_label": GOAL_LABEL.get(dp.goal.value, dp.goal.value),
        "targets": {
            "bmr": dp.bmr, "tdee": dp.tdee,
            "calories": dp.target_calories, "protein_g": dp.protein_g,
            "carbs_g": dp.carbs_g, "fats_g": dp.fats_g,
            "water_litres": dp.water_litres,
            "bmi": full["bmi"], "bmi_band": full["bmi_band"],
        },
        "current_weight_kg": ms.weight_kg,
        "target_weight_kg": ms.target_weight_kg,
        "estimated_weeks_to_target": full["estimated_weeks_to_target"],
        "chart": dp.chart or full["chart"],
        "tips": full["tips"],
        "avoid": full["avoid"],
        "disclaimer": full["disclaimer"],
    }


@router.get("/diet/{membership_code}")
def get_diet(membership_code: str, db: DbSession, user: CurrentUser):
    data = _load_diet(membership_code, db, user)
    # member_name/gym_name are only needed by the PDF renderer, not this
    # existing response shape - drop them so nothing else has to change.
    data.pop("member_name", None)
    data.pop("gym_name", None)
    return data


@router.get("/diet/{membership_code}/pdf")
def download_diet_pdf(membership_code: str, db: DbSession, user: CurrentUser):
    """Same data as GET /diet/{code}, rendered as a downloadable PDF."""
    from ..services.pdf_service import build_diet_chart_pdf

    data = _load_diet(membership_code, db, user)
    pdf_bytes = build_diet_chart_pdf(
        member_name=data["member_name"],
        gym_name=data["gym_name"],
        membership_code=data["membership_code"],
        goal_label=data["goal_label"],
        targets=data["targets"],
        current_weight_kg=data["current_weight_kg"],
        target_weight_kg=data["target_weight_kg"],
        estimated_weeks_to_target=data["estimated_weeks_to_target"],
        chart=data["chart"],
        tips=data["tips"],
        avoid=data["avoid"],
        disclaimer=data["disclaimer"],
    )
    filename = f"Fitora-Diet-Chart-{data['membership_code']}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ----------------------------------------------------------- my memberships
@router.get("/my/memberships")
def my_memberships(db: DbSession, user: CurrentUser):
    from ..services.dues_service import evaluate

    rows = (db.query(Membership)
            .filter(Membership.user_id == user.id)
            .order_by(Membership.created_at.desc()).all())

    out = []
    for m in rows:
        gym = db.get(Gym, m.gym_id)
        plan = db.get(GymPlan, m.plan_id) if m.plan_id else None
        ep = db.query(EntryPass).filter(EntryPass.membership_id == m.id).first()
        info = evaluate(m)
        out.append({
            "membership_code": m.membership_code,
            "status": m.status.value,
            "gym": {"gym_code": gym.gym_code, "name": gym.name,
                    "locality": gym.locality, "cover_image": gym.cover_image,
                    "phone": gym.phone} if gym else None,
            "plan": plan.plan_name if plan else None,
            "with_coach": m.with_coach,
            "total_amount": m.total_amount,
            "start_date": m.start_date.isoformat() if m.start_date else None,
            "end_date": m.end_date.isoformat() if m.end_date else None,
            "next_due_date": m.next_due_date.isoformat() if m.next_due_date else None,
            "days_remaining": ((m.end_date - date.today()).days
                               if m.end_date else None),
            "has_pass": ep is not None and ep.is_active,
            "pass_code": ep.pass_code if ep else None,
            "due_info": info.as_dict() if info else None,
        })
    return {"memberships": out, "total": len(out)}


# ------------------------------------------------------- gate-side scanning
class ScanRequest(BaseModel):
    qr_payload: str


@router.post("/scan")
def scan_pass(payload: ScanRequest, request: Request, db: DbSession):
    """
    Open endpoint for the gym's gate device. The QR is HMAC-signed, so
    verification does not need a login; we still cross-check live status.

    The signature only proves the payload was minted by this server - it
    does not make the payload's own copies of validity dates / coach flag
    trustworthy forever (e.g. if PASS_QR_SECRET were ever to leak, someone
    who still holds a genuinely-issued pass_code could otherwise re-sign a
    tampered copy of it with extended dates). So once the pass_code is
    resolved, every fact that matters for the entry decision is re-read from
    the live Membership/EntryPass rows, not from the signed JSON.
    """
    from ..services.pass_service import verify_scan

    rate_limit_scan(request)
    verdict = verify_scan(payload.qr_payload)
    if not verdict["valid"]:
        return verdict

    data = verdict["data"]
    ep = db.query(EntryPass).filter(EntryPass.pass_code == data["pc"]).first()
    if not ep:
        return {"valid": False, "reason": "unknown_pass",
                "message": "This pass is not in the system."}
    if not ep.is_active:
        return {"valid": False, "reason": "revoked",
                "message": "This pass has been deactivated. Contact the gym."}

    ms = db.get(Membership, ep.membership_id)
    if not ms:
        return {"valid": False, "reason": "unknown_pass",
                "message": "This pass is not linked to a membership."}
    if ms.status in (MembershipStatus.overdue, MembershipStatus.removed):
        return {
            "valid": False, "reason": ms.status.value,
            "message": ("Membership payment is overdue - entry blocked."
                        if ms.status is MembershipStatus.overdue
                        else "This membership has been removed."),
        }

    today = date.today()
    if today < ep.valid_from or today > ep.valid_until:
        return {
            "valid": False,
            "reason": "expired" if today > ep.valid_until else "not_started",
            "message": (f"This membership expired on {ep.valid_until.strftime('%d %b %Y')}."
                        if today > ep.valid_until else
                        f"This membership starts on {ep.valid_from.strftime('%d %b %Y')}."),
        }

    ep.scan_count = (ep.scan_count or 0) + 1
    ep.last_scanned_at = datetime.utcnow()
    db.commit()

    days_left = (ep.valid_until - today).days
    return {
        "valid": True,
        "reason": "ok",
        "days_remaining": days_left,
        "expiring_soon": days_left <= 7,
        "scan_count": ep.scan_count,
        "member": {
            "name": data["un"],
            "goal": GOAL_LABEL.get(data["gl"], data["gl"]),
            "plan": data["pl"],
            "with_coach": ms.with_coach,   # from the DB, not the signed copy
            "photo_url": ep.photo_url,
        },
        "message": f"Valid - {data['un']} | {data['pl']} | {days_left} days remaining",
    }
