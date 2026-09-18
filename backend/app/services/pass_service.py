"""
Fitora - Digital Entry Pass.

After a successful payment the member gets a pass carrying:
  * their photo
  * a signed QR code
  * the gym, plan, validity and their training goal

The QR payload is HMAC-signed, so a gym's scanner can verify it offline and a
screenshot of someone else's pass cannot be edited into a valid one.
"""
from __future__ import annotations
import base64
import io
from datetime import date, datetime
from typing import Any

import qrcode
from qrcode.image.styledpil import StyledPilImage
from qrcode.image.styles.moduledrawers.pil import RoundedModuleDrawer
from qrcode.image.styles.colormasks import SolidFillColorMask

from ..core.security import sign_pass_payload, verify_pass_payload, generate_code


def new_pass_code() -> str:
    return generate_code("FTP-", 10)


def build_qr_payload(
    *,
    pass_code: str,
    membership_code: str,
    user_id: int,
    user_name: str,
    gym_code: str,
    gym_name: str,
    goal: str,
    plan_name: str,
    with_coach: bool,
    valid_from: date,
    valid_until: date,
) -> str:
    """Compact signed token - kept small so the QR stays low-density and scans fast."""
    return sign_pass_payload({
        "v": 1,
        "pc": pass_code,
        "mc": membership_code,
        "uid": user_id,
        "un": user_name,
        "gc": gym_code,
        "gn": gym_name,
        "gl": goal,
        "pl": plan_name,
        "co": 1 if with_coach else 0,
        "vf": valid_from.isoformat(),
        "vu": valid_until.isoformat(),
    })


def render_qr_png(payload: str, *, box_size: int = 10, styled: bool = True) -> bytes:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=2,
    )
    qr.add_data(payload)
    qr.make(fit=True)

    if styled:
        img = qr.make_image(
            image_factory=StyledPilImage,
            module_drawer=RoundedModuleDrawer(),
            color_mask=SolidFillColorMask(
                back_color=(255, 255, 255), front_color=(17, 19, 24)
            ),
        )
    else:
        img = qr.make_image(fill_color="#111318", back_color="white")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def render_qr_data_uri(payload: str, *, box_size: int = 10) -> str:
    png = render_qr_png(payload, box_size=box_size)
    return "data:image/png;base64," + base64.b64encode(png).decode()


def verify_scan(payload: str, *, today: date | None = None) -> dict[str, Any]:
    """
    What a gym's scanner calls. Returns a verdict the gate staff can act on
    without needing to interpret anything.
    """
    data = verify_pass_payload(payload)
    if data is None:
        return {"valid": False, "reason": "invalid_signature",
                "message": "This pass is not genuine or has been tampered with."}

    today = today or date.today()
    try:
        vf = date.fromisoformat(data["vf"])
        vu = date.fromisoformat(data["vu"])
    except Exception:
        return {"valid": False, "reason": "malformed",
                "message": "Pass data could not be read."}

    if today < vf:
        return {"valid": False, "reason": "not_started", "data": data,
                "message": f"This membership starts on {vf.strftime('%d %b %Y')}."}
    if today > vu:
        return {"valid": False, "reason": "expired", "data": data,
                "message": f"This membership expired on {vu.strftime('%d %b %Y')}."}

    days_left = (vu - today).days
    return {
        "valid": True,
        "reason": "ok",
        "data": data,
        "days_remaining": days_left,
        "expiring_soon": days_left <= 7,
        "message": f"Valid - {data['un']} | {data['pl']} | {days_left} days remaining",
    }


def build_pass_view(
    *,
    pass_code: str,
    qr_payload: str,
    user_name: str,
    user_photo_url: str | None,
    member_since: date,
    gym_name: str,
    gym_locality: str,
    gym_phone: str,
    plan_name: str,
    goal_label: str,
    with_coach: bool,
    coach_name: str | None,
    valid_from: date,
    valid_until: date,
    amount_paid: int,
) -> dict[str, Any]:
    """Everything the pass card needs to render, in one payload."""
    today = date.today()
    days_left = (valid_until - today).days
    return {
        "pass_code": pass_code,
        "qr_data_uri": render_qr_data_uri(qr_payload),
        "member": {
            "name": user_name,
            "photo_url": user_photo_url,
            "member_since": member_since.isoformat(),
            "goal": goal_label,
        },
        "gym": {
            "name": gym_name,
            "locality": gym_locality,
            "phone": gym_phone,
        },
        "membership": {
            "plan": plan_name,
            "with_coach": with_coach,
            "coach_name": coach_name,
            "amount_paid": amount_paid,
            "valid_from": valid_from.isoformat(),
            "valid_until": valid_until.isoformat(),
            "days_remaining": max(0, days_left),
            "status": ("active" if days_left > 7 else
                       "expiring_soon" if days_left >= 0 else "expired"),
        },
        "issued_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }
