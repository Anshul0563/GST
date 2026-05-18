from __future__ import annotations

import base64
import hashlib
import hmac
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from uuid import uuid4

from app.core.config import Settings


@dataclass(frozen=True)
class Plan:
    id: str
    name: str
    monthly_paise: int
    yearly_paise: int
    features: tuple[str, ...]


PLANS: dict[str, Plan] = {
    "starter": Plan(
        id="starter",
        name="Starter",
        monthly_paise=99900,
        yearly_paise=999900,
        features=("3 GST profiles", "Marketplace imports", "GSTR-1 JSON/Excel", "Email support"),
    ),
    "growth": Plan(
        id="growth",
        name="Growth",
        monthly_paise=249900,
        yearly_paise=2499000,
        features=("10 GST profiles", "Tally XML", "2A/2B reconciliation", "Priority parser support"),
    ),
    "scale": Plan(
        id="scale",
        name="Scale",
        monthly_paise=499900,
        yearly_paise=4999000,
        features=("Unlimited GST profiles", "Bulk imports", "Advanced audit logs", "Priority support"),
    ),
}


def public_plans() -> list[dict[str, object]]:
    return [
        {
            "id": plan.id,
            "name": plan.name,
            "monthly_amount": plan.monthly_paise / 100,
            "yearly_amount": plan.yearly_paise / 100,
            "currency": "INR",
            "features": list(plan.features),
        }
        for plan in PLANS.values()
    ]


def plan_amount_paise(plan_id: str, billing_cycle: str) -> int:
    plan = PLANS.get(plan_id)
    if not plan:
        raise ValueError("Unknown billing plan")
    return plan.yearly_paise if billing_cycle == "yearly" else plan.monthly_paise


def create_razorpay_order(settings: Settings, amount_paise: int, receipt: str) -> dict[str, object]:
    if not settings.razorpay_key_id or not settings.razorpay_key_secret:
        return {
            "id": f"local_{uuid4().hex}",
            "amount": amount_paise,
            "currency": "INR",
            "receipt": receipt,
            "status": "created",
            "gateway_configured": False,
        }

    payload = json.dumps({
        "amount": amount_paise,
        "currency": "INR",
        "receipt": receipt,
        "payment_capture": 1,
    }).encode()
    token = base64.b64encode(f"{settings.razorpay_key_id}:{settings.razorpay_key_secret}".encode()).decode()
    request = urllib.request.Request(
        "https://api.razorpay.com/v1/orders",
        data=payload,
        headers={"Authorization": f"Basic {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"Razorpay order failed: {detail}") from exc


def verify_razorpay_signature(settings: Settings, order_id: str, payment_id: str, signature: str) -> bool:
    if not settings.razorpay_key_secret:
        return False
    payload = f"{order_id}|{payment_id}".encode()
    expected = hmac.new(settings.razorpay_key_secret.encode(), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
