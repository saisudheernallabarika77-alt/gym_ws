"""
Fitora - Dues & overdue engine.

Lifecycle of a renewal, exactly as specified:

    active  --(due date passes)-->  due  --(grace expires)-->  overdue
                                     |                            |
                              warning email sent            appears in the
                              WARNING_DAYS_BEFORE_DUE       Dues list on BOTH
                              and again on the due date     the admin portal and
                                                            the gym owner portal

Who can do what:
  * gym owner  - READ the dues list, raise a complaint. Nothing else.
  * admin      - extend the grace period, or remove the member. Only the admin
                 can change anything about a defaulting member.
"""
from __future__ import annotations
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Iterable

from ..core.config import settings
from ..db.models import Membership, MembershipStatus


@dataclass
class DueInfo:
    membership_id: int
    membership_code: str
    user_id: int
    gym_id: int
    amount: int
    due_date: date
    grace_days: int
    grace_ends_on: date
    days_overdue: int
    days_left_in_grace: int
    state: str             # upcoming | due | overdue
    warning_sent: bool
    severity: str          # none | low | medium | high | critical

    def as_dict(self) -> dict[str, Any]:
        return {
            "membership_id": self.membership_id,
            "membership_code": self.membership_code,
            "user_id": self.user_id,
            "gym_id": self.gym_id,
            "amount": self.amount,
            "due_date": self.due_date.isoformat(),
            "grace_days": self.grace_days,
            "grace_ends_on": self.grace_ends_on.isoformat(),
            "days_overdue": self.days_overdue,
            "days_left_in_grace": self.days_left_in_grace,
            "state": self.state,
            "warning_sent": self.warning_sent,
            "severity": self.severity,
        }


def _severity(state: str, days_overdue: int, days_left_in_grace: int) -> str:
    if state == "upcoming":
        return "none"
    if state == "due":
        return "low" if days_left_in_grace > 3 else "medium"
    if days_overdue <= 7:
        return "high"
    return "critical"


def evaluate(membership: Membership, *, today: date | None = None) -> DueInfo | None:
    """Classify one membership's payment state. None if nothing is owed."""
    today = today or date.today()
    if membership.status in (
        MembershipStatus.cancelled, MembershipStatus.removed,
        MembershipStatus.pending_payment,
    ):
        return None
    if not membership.next_due_date:
        return None

    due = membership.next_due_date
    grace = membership.grace_days or settings.DEFAULT_GRACE_DAYS
    grace_end = due + timedelta(days=grace)

    if today < due - timedelta(days=settings.WARNING_DAYS_BEFORE_DUE):
        return None                                  # not close enough to matter

    if today < due:
        state, days_overdue, left = "upcoming", 0, (due - today).days
    elif today <= grace_end:
        state, days_overdue, left = "due", (today - due).days, (grace_end - today).days
    else:
        state, days_overdue, left = "overdue", (today - due).days, 0

    amount = (membership.base_fee or 0) + (membership.coach_fee or 0)

    return DueInfo(
        membership_id=membership.id,
        membership_code=membership.membership_code,
        user_id=membership.user_id,
        gym_id=membership.gym_id,
        amount=amount,
        due_date=due,
        grace_days=grace,
        grace_ends_on=grace_end,
        days_overdue=days_overdue,
        days_left_in_grace=left,
        state=state,
        warning_sent=membership.warning_sent_at is not None,
        severity=_severity(state, days_overdue, left),
    )


def target_status(info: DueInfo) -> MembershipStatus:
    return {
        "upcoming": MembershipStatus.active,
        "due": MembershipStatus.due,
        "overdue": MembershipStatus.overdue,
    }[info.state]


def run_daily_sweep(
    session,
    *,
    today: date | None = None,
    send_warnings: bool = True,
) -> dict[str, Any]:
    """
    Nightly job: re-classify every live membership, flip statuses, and send
    one warning email per member per cycle. Safe to run repeatedly - warnings
    are gated on `warning_sent_at`.
    """
    from ..db.models import User, Gym
    from .email_service import send_due_warning

    today = today or date.today()
    live = (
        session.query(Membership)
        .filter(Membership.status.in_([
            MembershipStatus.active, MembershipStatus.due, MembershipStatus.overdue,
        ]))
        .all()
    )

    stats = {"checked": len(live), "marked_due": 0, "marked_overdue": 0,
             "warnings_sent": 0, "unchanged": 0}

    for m in live:
        info = evaluate(m, today=today)
        if info is None:
            stats["unchanged"] += 1
            continue

        new_status = target_status(info)
        if new_status != m.status:
            m.status = new_status
            if new_status is MembershipStatus.due:
                stats["marked_due"] += 1
            elif new_status is MembershipStatus.overdue:
                stats["marked_overdue"] += 1
        else:
            stats["unchanged"] += 1

        should_warn = (
            send_warnings
            and info.state in ("upcoming", "due")
            and m.warning_sent_at is None
        )
        if should_warn:
            user = session.get(User, m.user_id)
            gym = session.get(Gym, m.gym_id)
            if user and gym:
                send_due_warning(
                    user.email, user.full_name, gym.name,
                    info.due_date.strftime("%d %b %Y"),
                    info.amount, info.grace_days,
                )
                m.warning_sent_at = datetime.utcnow()
                stats["warnings_sent"] += 1

    session.commit()
    stats["run_date"] = today.isoformat()
    return stats


def dues_for_gym(session, gym_id: int, *, today: date | None = None) -> list[dict[str, Any]]:
    """Read-only dues list for a gym owner's portal."""
    from ..db.models import User

    rows = (
        session.query(Membership, User)
        .join(User, User.id == Membership.user_id)
        .filter(Membership.gym_id == gym_id)
        .filter(Membership.status.in_([
            MembershipStatus.active, MembershipStatus.due, MembershipStatus.overdue,
        ]))
        .all()
    )
    out = []
    for m, u in rows:
        info = evaluate(m, today=today)
        if info is None or info.state == "upcoming":
            continue
        out.append({
            **info.as_dict(),
            "user": {
                "id": u.id, "name": u.full_name,
                "phone": u.phone, "email": u.email, "photo_url": u.photo_url,
            },
            "paid": False,
        })
    return sorted(out, key=lambda r: -r["days_overdue"])


def gym_payment_summary(session, gym_id: int, *, today: date | None = None) -> dict[str, Any]:
    """'Who paid, who did not, how many members' - the snapshot both portals show."""
    rows = (
        session.query(Membership)
        .filter(Membership.gym_id == gym_id)
        .filter(Membership.status != MembershipStatus.removed)
        .all()
    )
    paid = due = overdue = 0
    pending_amount = 0
    for m in rows:
        info = evaluate(m, today=today)
        if info is None or info.state == "upcoming":
            if m.status is MembershipStatus.active:
                paid += 1
            continue
        if info.state == "due":
            due += 1
        else:
            overdue += 1
        pending_amount += info.amount

    return {
        "gym_id": gym_id,
        "total_members": len(rows),
        "paid_members": paid,
        "due_members": due,
        "overdue_members": overdue,
        "pending_amount": pending_amount,
        "as_of": (today or date.today()).isoformat(),
    }


# -------------------------------------------------- admin-only interventions
def extend_grace(session, membership_id: int, extra_days: int, admin_id: int,
                 reason: str = "") -> dict[str, Any]:
    from ..db.models import AuditLog

    m = session.get(Membership, membership_id)
    if not m:
        raise ValueError("membership not found")

    m.grace_days = (m.grace_days or settings.DEFAULT_GRACE_DAYS) + extra_days
    info = evaluate(m)
    if info:
        m.status = target_status(info)
    m.warning_sent_at = None      # let the next cycle warn again

    session.add(AuditLog(
        actor_type="admin", actor_id=admin_id, action="extend_grace",
        entity_type="membership", entity_id=str(membership_id),
        details={"extra_days": extra_days, "reason": reason,
                 "new_grace_days": m.grace_days},
    ))
    session.commit()
    return {"membership_id": membership_id, "grace_days": m.grace_days,
            "status": m.status.value}


def remove_member(session, membership_id: int, admin_id: int,
                  reason: str) -> dict[str, Any]:
    from ..db.models import AuditLog, Gym, EntryPass

    m = session.get(Membership, membership_id)
    if not m:
        raise ValueError("membership not found")

    m.status = MembershipStatus.removed
    m.removed_reason = reason

    ep = session.query(EntryPass).filter(EntryPass.membership_id == membership_id).first()
    if ep:
        ep.is_active = False       # pass stops scanning immediately

    gym = session.get(Gym, m.gym_id)
    if gym and gym.member_count:
        gym.member_count -= 1

    session.add(AuditLog(
        actor_type="admin", actor_id=admin_id, action="remove_member",
        entity_type="membership", entity_id=str(membership_id),
        details={"reason": reason, "gym_id": m.gym_id, "user_id": m.user_id},
    ))
    session.commit()
    return {"membership_id": membership_id, "status": "removed", "reason": reason}
