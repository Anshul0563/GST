from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.services.validation import SUPPORTED_RATES, money, round_money


@dataclass
class GstRateResolution:
    rate: Decimal | None
    confidence: str
    warning: str | None = None


def nearest_supported_rate(rate: Decimal, tolerance: Decimal = Decimal("0.25")) -> Decimal | None:
    normalized = money(rate)
    if normalized in SUPPORTED_RATES:
        return normalized
    nearest = min(SUPPORTED_RATES, key=lambda slab: abs(slab - normalized))
    return nearest if abs(nearest - normalized) <= tolerance else None


def resolve_gst_rate(row: dict[str, Any]) -> GstRateResolution:
    source_rate = money(row.get("gst_rate"))
    if Decimal("0.00") < source_rate < Decimal("1.00"):
        slab = nearest_supported_rate(round_money(source_rate * Decimal("100")))
        if slab is not None:
            return GstRateResolution(slab, "source_fraction_rate")
    if source_rate in SUPPORTED_RATES:
        return GstRateResolution(source_rate, "source_rate")

    taxable = abs(money(row.get("taxable_value")))
    tax = abs(money(row.get("igst")) + money(row.get("cgst")) + money(row.get("sgst")) + money(row.get("cess")))
    if taxable == Decimal("0.00") and tax == Decimal("0.00"):
        return GstRateResolution(Decimal("0.00"), "zero_amount_skip", "Zero taxable and zero GST row")
    if taxable > Decimal("0.00") and tax > Decimal("0.00"):
        derived = round_money(tax * Decimal("100") / taxable)
        slab = nearest_supported_rate(derived)
        if slab is not None:
            return GstRateResolution(slab, "derived_from_tax", f"Derived GST rate {derived} normalized to {slab}")
        return GstRateResolution(None, "unresolved", f"Derived GST rate {derived} is outside supported slabs")

    slab = nearest_supported_rate(source_rate)
    if slab is not None:
        return GstRateResolution(slab, "source_rate_nearest", f"GST rate {source_rate} normalized to {slab}")
    return GstRateResolution(None, "unresolved", "GST rate could not be resolved")
