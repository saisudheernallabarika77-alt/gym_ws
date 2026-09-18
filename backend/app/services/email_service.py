"""
Fitora - Email / OTP delivery over SMTP.

When SMTP credentials are not configured the OTP is logged to the console
instead of being sent, so the whole signup flow works locally with no setup.
Set SMTP_ENABLED=true plus SMTP_USER / SMTP_PASSWORD (a Gmail app password)
to send real mail.
"""
from __future__ import annotations
import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from ..core.config import settings

log = logging.getLogger(__name__)

BRAND = "#FF4D2E"


def _shell(title: str, intro: str, body_html: str, footer: str = "") -> str:
    return f"""<!doctype html>
<html><body style="margin:0;padding:0;background:#0f1115;font-family:system-ui,-apple-system,'Segoe UI',Roboto,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#0f1115;padding:32px 16px;">
    <tr><td align="center">
      <table width="100%" style="max-width:520px;background:#16181d;border-radius:16px;overflow:hidden;border:1px solid #23262d;">
        <tr><td style="background:linear-gradient(135deg,{BRAND},#FF8A3D);padding:26px 28px;">
          <div style="font-size:24px;font-weight:800;color:#fff;letter-spacing:-0.5px;">FITORA</div>
          <div style="font-size:12px;color:rgba(255,255,255,.85);margin-top:2px;">Find your gym. Join in minutes.</div>
        </td></tr>
        <tr><td style="padding:30px 28px;color:#e6e8ec;">
          <h2 style="margin:0 0 10px;font-size:19px;color:#fff;font-weight:700;">{title}</h2>
          <p style="margin:0 0 22px;font-size:14px;line-height:1.6;color:#a8adb8;">{intro}</p>
          {body_html}
          <p style="margin:22px 0 0;font-size:12px;line-height:1.6;color:#6c727f;">{footer}</p>
        </td></tr>
        <tr><td style="padding:16px 28px;background:#111318;border-top:1px solid #23262d;
                       font-size:11px;color:#5a606c;text-align:center;">
          &copy; 2026 Fitora &middot; Kakinada, Andhra Pradesh<br>
          This is an automated message, please do not reply.
        </td></tr>
      </table>
    </td></tr>
  </table>
</body></html>"""


def _otp_html(code: str, purpose_label: str) -> str:
    boxes = "".join(
        f'<span style="display:inline-block;width:44px;height:56px;line-height:56px;margin:0 4px;'
        f'background:#1e2128;border:1px solid #2e323b;border-radius:10px;font-size:26px;'
        f'font-weight:800;color:#fff;text-align:center;">{d}</span>'
        for d in code
    )
    return _shell(
        title=f"Your {purpose_label} code",
        intro="Enter this 6-digit code to continue. It is valid for "
              f"{settings.OTP_TTL_MINUTES} minutes.",
        body_html=f'<div style="text-align:center;margin:8px 0 4px;">{boxes}</div>',
        footer="If you did not request this code, you can safely ignore this email. "
               "Never share this code with anyone.",
    )


def _send(to_email: str, subject: str, html: str, text: str) -> bool:
    if not (settings.SMTP_ENABLED and settings.SMTP_USER and settings.SMTP_PASSWORD):
        log.warning("SMTP disabled - email to %s not sent. Subject: %s", to_email, subject)
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL or settings.SMTP_USER}>"
    msg["To"] = to_email
    msg.attach(MIMEText(text, "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        ctx = ssl.create_default_context()
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as server:
            server.ehlo()
            server.starttls(context=ctx)
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(msg)
        log.info("email sent to %s (%s)", to_email, subject)
        return True
    except Exception as e:
        log.error("SMTP send failed for %s: %s", to_email, e)
        return False


# ------------------------------------------------------------------- public
def send_otp_email(to_email: str, code: str, purpose: str = "signup") -> bool:
    labels = {
        "signup": "Fitora signup verification",
        "login": "Fitora login verification",
        "password_reset": "Fitora password reset",
        "gym_owner_signup": "Fitora gym partner verification",
    }
    label = labels.get(purpose, "Fitora verification")
    sent = _send(
        to_email,
        subject=f"{code} is your Fitora verification code",
        html=_otp_html(code, label),
        text=(f"Your Fitora verification code is {code}. "
              f"It expires in {settings.OTP_TTL_MINUTES} minutes. "
              f"Do not share this code with anyone."),
    )
    if not sent:
        # dev fallback so the flow is always testable
        log.warning("=" * 58)
        log.warning("  FITORA OTP (dev mode - email not sent)")
        log.warning("  to      : %s", to_email)
        log.warning("  purpose : %s", purpose)
        log.warning("  CODE    : %s", code)
        log.warning("=" * 58)
        print(f"\n{'=' * 58}\n  FITORA OTP  ->  {to_email}  [{purpose}]\n"
              f"  CODE: {code}\n{'=' * 58}\n", flush=True)
    return sent


def send_welcome_email(to_email: str, name: str) -> bool:
    return _send(
        to_email,
        subject="Welcome to Fitora",
        html=_shell(
            title=f"Welcome, {name}",
            intro="Your Fitora account is verified and ready.",
            body_html=(
                '<p style="font-size:14px;line-height:1.7;color:#a8adb8;margin:0;">'
                "Ask our assistant things like <em>&ldquo;AC gym under Rs.1500 near me&rdquo;</em> "
                "and it will find gyms that actually match &mdash; with the coach fee shown "
                "clearly, included or separate.</p>"
            ),
            footer="Happy training.",
        ),
        text=f"Welcome to Fitora, {name}. Your account is verified.",
    )


def send_membership_confirmation(to_email: str, name: str, gym_name: str,
                                 pass_code: str, valid_until: str, amount: int) -> bool:
    body = (
        f'<table width="100%" cellpadding="0" cellspacing="0" style="font-size:14px;color:#e6e8ec;">'
        f'<tr><td style="padding:6px 0;color:#8b909b;">Gym</td>'
        f'<td style="padding:6px 0;text-align:right;font-weight:600;">{gym_name}</td></tr>'
        f'<tr><td style="padding:6px 0;color:#8b909b;">Amount paid</td>'
        f'<td style="padding:6px 0;text-align:right;font-weight:600;">Rs.{amount}</td></tr>'
        f'<tr><td style="padding:6px 0;color:#8b909b;">Valid until</td>'
        f'<td style="padding:6px 0;text-align:right;font-weight:600;">{valid_until}</td></tr>'
        f'<tr><td style="padding:6px 0;color:#8b909b;">Pass code</td>'
        f'<td style="padding:6px 0;text-align:right;font-weight:700;color:{BRAND};">{pass_code}</td></tr>'
        f'</table>'
    )
    return _send(
        to_email,
        subject=f"You're in - {gym_name} membership confirmed",
        html=_shell(
            title="Membership confirmed",
            intro=f"{name}, your digital entry pass is ready in the Fitora app.",
            body_html=body,
            footer="Show the QR code on your pass at the gym entrance.",
        ),
        text=(f"Membership confirmed at {gym_name}. Pass code {pass_code}, "
              f"valid until {valid_until}. Amount paid Rs.{amount}."),
    )


def send_due_warning(to_email: str, name: str, gym_name: str,
                     due_date: str, amount: int, grace_days: int) -> bool:
    body = (
        f'<div style="background:#2a1a13;border:1px solid #5a3420;border-radius:12px;padding:16px;">'
        f'<div style="font-size:13px;color:#ffb27a;font-weight:600;margin-bottom:6px;">Payment due</div>'
        f'<div style="font-size:14px;color:#e6e8ec;line-height:1.7;">'
        f'Rs.<b>{amount}</b> for <b>{gym_name}</b> was due on <b>{due_date}</b>.<br>'
        f'You have <b>{grace_days} days</b> to pay before your membership is marked overdue.'
        f'</div></div>'
    )
    return _send(
        to_email,
        subject=f"Payment reminder - {gym_name}",
        html=_shell(
            title="Your membership payment is due",
            intro=f"Hi {name}, this is a reminder about your pending gym fee.",
            body_html=body,
            footer="Pay from the Fitora app to keep your entry pass active.",
        ),
        text=(f"Payment reminder: Rs.{amount} for {gym_name} was due {due_date}. "
              f"{grace_days} days of grace remain."),
    )


# Auto-generated wording per complaint category, used when the admin sends a
# warning without typing a custom message. Kept short and factual - the
# admin's own note (if any) is appended below this in the email body.
_WARNING_TEMPLATES: dict[str, str] = {
    "payment_default": (
        "A gym you are a member of has reported that your membership payment "
        "is overdue. Please clear the pending amount from the Fitora app as "
        "soon as possible to avoid further action on your account."
    ),
    "misconduct": (
        "A gym you are a member of has raised a conduct complaint against "
        "you. Please review the gym's rules. Repeated complaints can lead to "
        "your membership being removed and your account being restricted."
    ),
    "damage": (
        "A gym you are a member of has reported damage to their equipment or "
        "property associated with your visits. Please get in touch with the "
        "gym directly to resolve this."
    ),
    "service_issue": (
        "A member has reported a service issue with your gym. Please review "
        "your facilities and member experience. Repeated complaints can "
        "affect your gym's standing on Fitora."
    ),
    "fraud": (
        "A member has raised a fraud or billing-dispute complaint against "
        "your gym. This is taken seriously - please be prepared to explain "
        "your pricing and charges if the admin follows up."
    ),
    "safety": (
        "A member has raised a safety concern about your gym. Please review "
        "your facilities and equipment condition promptly."
    ),
    "billing": (
        "A member has raised a billing complaint about your gym. Please "
        "ensure your published pricing matches what members are actually charged."
    ),
    "other": (
        "A complaint has been raised concerning your account on Fitora. "
        "Please review the details below."
    ),
}


def default_warning_message(category: str) -> str:
    """The auto-generated wording for a category, exposed so the admin UI
    can show/edit it before sending, or send it as-is."""
    return _WARNING_TEMPLATES.get(category, _WARNING_TEMPLATES["other"])


def send_complaint_warning(
    to_email: str, name: str, *, subject: str, message: str,
    complaint_category: str, admin_note: str | None = None,
) -> bool:
    """
    Sent by the admin from the Complaints screen, to either the user a gym
    owner complained about, or the gym owner a member complained about.
    `message` is either the auto-generated template (see
    default_warning_message) or whatever the admin typed - the caller
    decides which, this function just sends it.
    """
    body = (
        f'<div style="background:#2a1a13;border:1px solid #5a3420;border-radius:12px;padding:16px;">'
        f'<div style="font-size:13px;color:#ffb27a;font-weight:600;margin-bottom:6px;">'
        f'Warning &middot; {complaint_category.replace("_", " ").title()}</div>'
        f'<div style="font-size:14px;color:#e6e8ec;line-height:1.7;">{message}</div>'
        f'</div>'
        + (f'<p style="font-size:13px;color:#a8adb8;margin-top:14px;line-height:1.6;">'
           f'<b>Note from Fitora admin:</b> {admin_note}</p>' if admin_note else '')
    )
    return _send(
        to_email,
        subject=f"Fitora warning: {subject}",
        html=_shell(
            title="A warning has been issued on your account",
            intro=f"Hi {name},",
            body_html=body,
            footer="If you believe this is a mistake, reply to this email or contact Fitora support.",
        ),
        text=f"Fitora warning ({complaint_category}): {message}"
             + (f"\n\nAdmin note: {admin_note}" if admin_note else ""),
    )
