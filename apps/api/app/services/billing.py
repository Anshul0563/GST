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
    "online_seller": Plan(
        id="online_seller",
        name="GST Online Seller",
        monthly_paise=7900,
        yearly_paise=94800,
        features=("Marketplace imports", "Manage normalized sales data", "GSTR-1 JSON export", "GSTR-1 Excel reports"),
    ),
    "ecom_tally": Plan(
        id="ecom_tally",
        name="eCom to Tally",
        monthly_paise=19900,
        yearly_paise=238800,
        features=("Tally company setup", "Marketplace import", "Ledger mapping", "Tally XML and voucher Excel export"),
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
