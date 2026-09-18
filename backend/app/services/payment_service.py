"""
Fitora - Payments.

Money rule from the spec: members always pay the PLATFORM, never the gym
directly. Each successful payment is split into a platform commission and a
gym share; the gym share accumulates until the admin releases a monthly Payout.

Gateways sit behind one interface so swapping the mock for Razorpay is a
config change, not a rewrite.
"""
from __future__ import annotations
import random
import time
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from urllib.parse import quote

from ..core.config import settings
from ..core.security import generate_code


def new_payment_ref() -> str:
    return generate_code("FTPAY", 12)


def split_amount(amount: int, commission_percent: float | None = None) -> dict[str, int]:
    pct = settings.PLATFORM_COMMISSION_PERCENT if commission_percent is None else commission_percent
    commission = int(round(amount * pct / 100))
    return {
        "amount": amount,
        "platform_commission": commission,
        "gym_share": amount - commission,
        "commission_percent": pct,
    }


def build_upi_uri(*, payee_vpa: str, payee_name: str, amount: int, ref: str, note: str) -> str:
    """Standard UPI deep link - any UPI app opens this."""
    return (
        f"upi://pay?pa={quote(payee_vpa)}&pn={quote(payee_name)}"
        f"&am={amount}&cu=INR&tr={quote(ref)}&tn={quote(note[:50])}"
    )


# --------------------------------------------------------------- interface
class PaymentGateway(ABC):
    name: str

    @abstractmethod
    def create_order(self, *, amount: int, ref: str, description: str,
                     customer: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    def confirm(self, *, ref: str, gateway_payload: dict[str, Any]) -> dict[str, Any]: ...


# -------------------------------------------------------------------- mock
class MockUPIGateway(PaymentGateway):
    """
    Development gateway. Produces a real, scannable UPI deep link and QR so the
    checkout screen looks and behaves like production, then simulates the bank
    response. No real money moves.
    """
    name = "mock"
    FAILURE_RATE = 0.0    # set >0 to exercise failure handling

    def create_order(self, *, amount: int, ref: str, description: str,
                     customer: dict[str, Any]) -> dict[str, Any]:
        upi_uri = build_upi_uri(
            payee_vpa=settings.PLATFORM_UPI_ID,
            payee_name="Fitora",
            amount=amount,
            ref=ref,
            note=description,
        )
        from .pass_service import render_qr_data_uri
        return {
            "gateway": self.name,
            "order_id": f"order_{ref}",
            "ref": ref,
            "amount": amount,
            "currency": "INR",
            "upi_uri": upi_uri,
            "qr_data_uri": render_qr_data_uri(upi_uri, box_size=8),
            "payee_vpa": settings.PLATFORM_UPI_ID,
            "payee_name": "Fitora",
            "description": description,
            "apps": [
                {"name": "Google Pay", "scheme": upi_uri.replace("upi://", "gpay://upi/")},
                {"name": "PhonePe", "scheme": upi_uri.replace("upi://", "phonepe://")},
                {"name": "Paytm", "scheme": upi_uri.replace("upi://", "paytmmp://")},
                {"name": "Any UPI app", "scheme": upi_uri},
            ],
            "expires_in_seconds": 600,
            "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }

    def confirm(self, *, ref: str, gateway_payload: dict[str, Any]) -> dict[str, Any]:
        vpa = (gateway_payload or {}).get("upi_id", "")
        if vpa and "@" not in vpa:
            return {"status": "failed", "reason": "Invalid UPI ID format",
                    "gateway_txn_id": None}
        if self.FAILURE_RATE and random.random() < self.FAILURE_RATE:
            return {"status": "failed", "reason": "Payment declined by bank",
                    "gateway_txn_id": None}
        return {
            "status": "success",
            "gateway_txn_id": f"MOCKTXN{int(time.time())}{random.randint(100, 999)}",
            "upi_id": vpa or "user@upi",
            "completed_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }


# --------------------------------------------------------------- razorpay
class RazorpayGateway(PaymentGateway):
    """
    Real gateway. Kept intentionally thin: fill RAZORPAY_KEY_ID/SECRET and set
    PAYMENT_GATEWAY=razorpay to switch over. Signature verification below is
    the standard HMAC check from Razorpay's docs.
    """
    name = "razorpay"

    def create_order(self, *, amount: int, ref: str, description: str,
                     customer: dict[str, Any]) -> dict[str, Any]:
        import httpx
        resp = httpx.post(
            "https://api.razorpay.com/v1/orders",
            auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET),
            json={
                "amount": amount * 100,          # paise
                "currency": "INR",
                "receipt": ref,
                # "ref" here is how the webhook handler finds the matching
                # Payment row - Razorpay echoes `notes` back verbatim on
                # every webhook event for this payment.
                "notes": {"ref": ref, "description": description, **customer},
            },
            timeout=20,
        )
        resp.raise_for_status()
        order = resp.json()
        return {
            "gateway": self.name,
            "order_id": order["id"],
            "ref": ref,
            "amount": amount,
            "currency": "INR",
            "key_id": settings.RAZORPAY_KEY_ID,
            "description": description,
            "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
        }

    def confirm(self, *, ref: str, gateway_payload: dict[str, Any]) -> dict[str, Any]:
        """
        NOT the source of truth for Razorpay. This checks the checkout-time
        signature Razorpay's JS SDK hands back to the browser - useful for an
        optimistic "looks paid" UI update, but the browser/client controls
        every value going into this call, so a client could in principle
        skip the checkout and post a fabricated payload here. The only
        payload that would actually pass is one signed with RAZORPAY_KEY_SECRET,
        which the client never has - so this check is NOT forgeable, but it
        is still client-invoked, which is the property that matters: a
        client can simply choose not to call this endpoint's caller, or call
        it multiple times, or (if this secret ever leaked) fabricate a
        payload offline with no live transaction behind it at all.
        The actual money movement is confirmed exclusively by the
        `razorpay_webhook` handler below, called by Razorpay's servers
        directly over a channel the client never touches. See
        `verify_webhook_signature` / the /webhooks/razorpay route.
        """
        import hashlib, hmac
        order_id = gateway_payload.get("razorpay_order_id", "")
        payment_id = gateway_payload.get("razorpay_payment_id", "")
        signature = gateway_payload.get("razorpay_signature", "")
        expected = hmac.new(
            settings.RAZORPAY_KEY_SECRET.encode(),
            f"{order_id}|{payment_id}".encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            return {"status": "failed", "reason": "Signature verification failed",
                    "gateway_txn_id": None}
        return {
            "status": "pending_webhook",
            "gateway_txn_id": payment_id,
            "completed_at": None,
        }


def verify_razorpay_webhook_signature(body: bytes, signature: str) -> bool:
    """
    Verify the `X-Razorpay-Signature` header on an incoming webhook POST.
    This is the ONLY signature that should ever flip a Razorpay payment to
    `success` in the database - unlike the checkout signature above, this
    one is computed by Razorpay's servers over the raw webhook body and sent
    directly to this backend, with no client in the loop at all.
    """
    import hashlib, hmac
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        return False
    expected = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode(), body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature or "")


_GATEWAYS: dict[str, type[PaymentGateway]] = {
    "mock": MockUPIGateway,
    "razorpay": RazorpayGateway,
}


def get_gateway(name: str | None = None) -> PaymentGateway:
    key = (name or settings.PAYMENT_GATEWAY).lower()
    return _GATEWAYS.get(key, MockUPIGateway)()
