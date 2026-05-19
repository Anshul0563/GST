from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import json
from typing import Any

from app.services.validation import money, validate_gstin
from app.utils.states import (
    STATE_CODES,
    normalize_state_text,
    state_code_from_pincode,
    state_code_from_text,
)

STATE_ALIASES = [
    "billing state",
    "delivery state",
    "buyer state",
    "customer state",
    "ship to state",
    "shipping state",
    "ship state",
    "place of supply",
    "place of supply state",
    "pos",
    "state",
    "destination state",
    "recipient state",
    "buyer delivery state",
    "consignee state",
    "gst state",
    "state code",
    "dispatch state",
    "seller state",
    "order state",
    "customer_state",
    "delivery_state",
    "shipping_state",
    "recipient_state",
    "buyer_state",
    "place_of_supply",
    "ship-state",
    "ship_to_state",
    "ship-to-state",
    "recipient-state",
    "destination-state",
    "buyer-state",
    "place-of-supply",
    "shipping province",
    "billing province",
    "province",
    "customer province",
    "delivery province",
    "ship province",
    "shipping address province",
    "billing address province",
    "shipping address state",
    "billing address state",
    "ship to province",
    "ship to state code",
    "billing state code",
    "shipping state code",
    "destination state code",
    "place of supply code",
    "place_of_supply_state",
    "place_of_supply_code",
]

PINCODE_ALIASES = [
    "pincode",
    "pin code",
    "postal code",
    "zip",
    "zip code",
    "ship to postal code",
    "ship from postal code",
    "shipping pincode",
    "delivery pincode",
    "buyer pincode",
    "customer pincode",
    "recipient pincode",
    "shipping zip",
    "billing zip",
    "shipping postal code",
    "billing postal code",
    "delivery postal code",
]


@dataclass
class PosResolution:
    buyer_state_code: str | None
    buyer_state_name: str | None
    confidence: str
    source_column: str | None = None
    warning: str | None = None

    def model_dump(self) -> dict[str, str | None]:
        return {
            "buyer_state_code": self.buyer_state_code,
            "buyer_state_name": self.buyer_state_name,
            "confidence": self.confidence,
            "source_column": self.source_column,
            "warning": self.warning,
        }


def clean_key(value: object) -> str:
    text = "" if value is None else str(value)
    text = text.strip().lower()
    for char in ("_", "-", ".", "/", "\\", "\n", "\t"):
        text = text.replace(char, " ")
    return " ".join(text.split())


def flatten_row(row: Any, prefix: str = "") -> list[tuple[str, Any]]:
    if isinstance(row, dict):
        flattened: list[tuple[str, Any]] = []
        for key, value in row.items():
            next_key = f"{prefix}.{key}" if prefix else str(key)
            flattened.extend(flatten_row(value, next_key))
        return flattened
    if isinstance(row, list):
        flattened = []
        for index, value in enumerate(row):
            next_key = f"{prefix}.{index}" if prefix else str(index)
            flattened.extend(flatten_row(value, next_key))
        return flattened
    return [(prefix, row)]


def read_raw_json(normalized_row: dict[str, Any]) -> dict[str, Any]:
    raw = normalized_row.get("raw_row_json")
    if not raw:
        return {}
    try:
        parsed = json.loads(str(raw))
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def find_value(row: dict[str, Any], aliases: list[str]) -> tuple[str | None, Any]:
    alias_set = {clean_key(alias) for alias in aliases}
    flattened = flatten_row(row)
    for key, value in flattened:
        if value in (None, ""):
            continue
        cleaned = clean_key(key)
        if cleaned in alias_set:
            return key, value
    for key, value in flattened:
        if value in (None, ""):
            continue
        cleaned = clean_key(key)
        if any(alias in cleaned for alias in alias_set):
            return key, value
    return None, None


def resolve_pos(
    raw_row: dict[str, Any],
    normalized_row: dict[str, Any],
    platform: str,
    seller_gstin: str | None = None,
) -> PosResolution:
    existing_code = state_code_from_text(normalized_row.get("buyer_state_code"))
    if existing_code:
        return PosResolution(
            existing_code,
            STATE_CODES.get(existing_code),
            "normalized",
            "buyer_state_code",
        )

    existing_name_code = state_code_from_text(normalized_row.get("buyer_state_name"))
    if existing_name_code:
        return PosResolution(
            existing_name_code,
            STATE_CODES.get(existing_name_code),
            "normalized",
            "buyer_state_name",
        )

    search_rows = [raw_row, read_raw_json(normalized_row)]
    for source in search_rows:
        if not source:
            continue
        column, value = find_value(source, STATE_ALIASES)
        code = state_code_from_text(value)
        if code:
            return PosResolution(code, STATE_CODES.get(code), "high", column)

    for source in search_rows:
        if not source:
            continue
        column, value = find_value(source, PINCODE_ALIASES)
        code = state_code_from_pincode(value)
        if code:
            return PosResolution(
                code,
                STATE_CODES.get(code),
                "inferred_from_pincode",
                column,
                "POS inferred from pincode",
            )

    cgst = money(normalized_row.get("cgst"))
    sgst = money(normalized_row.get("sgst"))
    seller_gstin_value = (
        str(seller_gstin or normalized_row.get("gstin") or "").strip().upper()
    )
    seller_state = (
        seller_gstin_value[:2] if validate_gstin(seller_gstin_value) else None
    )
    if (cgst != Decimal("0.00") or sgst != Decimal("0.00")) and seller_state:
        return PosResolution(
            seller_state,
            STATE_CODES.get(seller_state),
            "inferred_from_seller_state",
            "gstin",
            "POS inferred from seller GSTIN because CGST/SGST is present",
        )

    return PosResolution(
        None, None, "unresolved", None, f"POS unresolved for {platform}"
    )


def new_pos_debug(platform: str) -> dict[str, Any]:
    return {
        "platform": platform,
        "header_rows": [],
        "detected_state_columns": [],
        "sample_state_values": [],
        "resolved_pos_count": 0,
        "inferred_from_pincode_count": 0,
        "unresolved_pos_count": 0,
        "unresolved_row_ids": [],
        "warnings": [],
    }


def observe_pos_debug(
    debug: dict[str, Any],
    row_id: Any,
    resolution: PosResolution,
    raw_row: dict[str, Any],
) -> None:
    if (
        resolution.source_column
        and resolution.source_column not in debug["detected_state_columns"]
    ):
        debug["detected_state_columns"].append(resolution.source_column)
    if resolution.source_column:
        value = None
        for key, candidate in flatten_row(raw_row):
            if key == resolution.source_column:
                value = candidate
                break
        if value not in (None, "") and len(debug["sample_state_values"]) < 5:
            debug["sample_state_values"].append({resolution.source_column: str(value)})
    if resolution.buyer_state_code:
        debug["resolved_pos_count"] += 1
        if resolution.confidence == "inferred_from_pincode":
            debug["inferred_from_pincode_count"] += 1
    else:
        debug["unresolved_pos_count"] += 1
        debug["unresolved_row_ids"].append(row_id)
    if resolution.warning:
        debug["warnings"].append({"row": row_id, "warning": resolution.warning})


def apply_pos_resolution(
    raw_row: dict[str, Any], normalized_row: dict[str, Any], platform: str
) -> PosResolution:
    resolution = resolve_pos(
        raw_row, normalized_row, platform, normalized_row.get("gstin")
    )
    normalized_row["buyer_state_code"] = resolution.buyer_state_code
    normalized_row["buyer_state_name"] = resolution.buyer_state_name
    return resolution
