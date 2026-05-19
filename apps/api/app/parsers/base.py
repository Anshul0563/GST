from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import json
import re
from typing import Any

import pandas as pd

from app.services.validation import money
from app.utils.states import STATE_CODES, state_code_from_text


ETINS = {
    "amazon": "07AAICA3918J1CV",
    "flipkart": "07AACCF0683K1CU",
    "meesho": "07AARCM9332R1CQ",
    "myntra": "29AADCM5146R1C1",
    "jiomart": "27AABCI6363G1C7",
    "snapdeal": "07AAICA4872D1C8",
    "custom": None,
}


@dataclass
class ParseResult:
    transactions: list[dict] = field(default_factory=list)
    errors: list[dict] = field(default_factory=list)


class MarketplaceParser:
    platform = "custom"

    def __init__(self, gstin: str, filing_period: str):
        self.gstin = gstin.upper()
        self.filing_period = filing_period

    def parse(self, files: list[Path]) -> ParseResult:
        raise NotImplementedError

    def normalize_row(self, row: dict[str, Any], source_file: str) -> dict:
        buyer_state_code = first_value(row, ["buyer_state_code", "pos", "place of supply", "ship to state", "ship state", "billing state", "buyer billing state", "buyer delivery state", "state"])
        buyer_state_code = state_code_from_text(buyer_state_code)
        raw_date = first_value(row, ["invoice_date", "invoice date", "invoice generated date", "shipment date", "order date", "date"])
        doc_type = str(first_value(row, ["doc_type", "document type", "transaction type", "type"]) or "invoice").lower()
        if "refund" in doc_type or "return" in doc_type or "credit" in doc_type:
            doc_type = "credit_note"
        elif "debit" in doc_type:
            doc_type = "debit_note"
        else:
            doc_type = "invoice"
        return {
            "platform": self.platform,
            "gstin": self.gstin,
            "etin": first_value(row, ["etin", "ecommerce gstin", "operator gstin"]) or ETINS.get(self.platform),
            "filing_period": self.filing_period,
            "order_id": text(first_value(row, ["order_id", "order id", "amazon order id", "order no"])),
            "order_item_id": text(first_value(row, ["order_item_id", "order item id", "order item identifier", "item id"])),
            "invoice_no": text(first_value(row, ["invoice_no", "invoice number", "invoice id", "invoice no", "tax invoice no"])),
            "invoice_date": parse_date(raw_date),
            "doc_type": doc_type,
            "buyer_state_code": buyer_state_code,
            "buyer_state_name": STATE_CODES.get(buyer_state_code or ""),
            "hsn": text(first_value(row, ["hsn", "hsn code", "hsn/sac"])),
            "product_name": text(first_value(row, ["product_name", "product title", "product name", "sku title", "item description"])),
            "sku": text(first_value(row, ["sku", "seller sku", "fsn", "merchant sku"])),
            "qty": money(first_value(row, ["qty", "quantity", "item quantity"])),
            "taxable_value": money(first_value(row, ["taxable_value", "taxable value", "taxable amount", "tax exclusive gross", "taxable sales", "price before tax", "taxable turnover"])),
            "gst_rate": money(first_value(row, ["gst_rate", "gst rate", "tax rate", "igst rate", "total tax rate"])),
            "igst": money(first_value(row, ["igst tax", "igst amount", "integrated tax", "igst"])),
            "cgst": money(first_value(row, ["cgst tax", "cgst amount", "central tax", "cgst"])),
            "sgst": money(first_value(row, ["sgst tax", "sgst amount", "state tax", "sgst"])),
            "cess": money(first_value(row, ["cess", "cess amount"])),
            "tcs": money(first_value(row, ["tcs", "tcs amount"])),
            "tds": money(first_value(row, ["tds", "tds amount"])),
            "gross_amount": money(first_value(row, ["gross_amount", "gross amount", "invoice amount", "total amount", "selling price", "price before discount"])),
            "discount_seller": money(first_value(row, ["discount_seller", "seller discount", "merchant discount"])),
            "discount_platform": money(first_value(row, ["discount_platform", "platform discount", "bank discount", "cashback"])),
            "settlement_amount": money(first_value(row, ["settlement_amount", "settlement amount", "net payable"])),
            "source_file": source_file,
            "raw_row_json": json.dumps(row, default=str),
        }


def clean_column(value: object) -> str:
    text_value = "" if value is None else str(value)
    text_value = re.sub(r"\s+", " ", text_value.strip().lower())
    return text_value.replace("\n", " ").replace("_", " ")


def text(value: object) -> str | None:
    if value is None:
        return None
    value = str(value).strip()
    if not value or value.lower() == "nan":
        return None
    return value


def parse_date(value: object):
    if value in (None, ""):
        return None
    text_value = str(value).strip()
    dayfirst = not bool(re.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}", text_value))
    parsed = pd.to_datetime(text_value, errors="coerce", dayfirst=dayfirst)
    if pd.isna(parsed):
        return None
    return parsed.date()


def should_skip_transaction(txn: dict[str, Any]) -> bool:
    if txn.get("invoice_no"):
        return False
    amount_fields = ("taxable_value", "gross_amount", "igst", "cgst", "sgst", "cess")
    return all(money(txn.get(field)) == 0 for field in amount_fields)


def first_value(row: dict[str, Any], candidates: list[str]) -> Any:
    lowered = {clean_column(k): v for k, v in row.items()}
    for candidate in candidates:
        if candidate in lowered and lowered[candidate] not in (None, ""):
            return lowered[candidate]
    for key, value in lowered.items():
        for candidate in candidates:
            if candidate in key and value not in (None, ""):
                return value
    return None


def unique_headers(headers: list[str]) -> list[str]:
    seen: dict[str, int] = {}
    result: list[str] = []
    for index, header in enumerate(headers):
        normalized = header or f"column {index}"
        count = seen.get(normalized, 0)
        seen[normalized] = count + 1
        result.append(normalized if count == 0 else f"{normalized} {count + 1}")
    return result


def detect_header_row_frame(raw: pd.DataFrame, required_tokens: list[str]) -> int:
    best_index = 0
    best_score = -1
    for idx, row in raw.head(40).iterrows():
        cells = " ".join(clean_column(value) for value in row.tolist())
        score = sum(1 for token in required_tokens if token in cells)
        non_empty = sum(1 for value in row.tolist() if str(value).strip() and str(value).lower() != "nan")
        score += min(non_empty, 8) / 20
        if score > best_score:
            best_score = score
            best_index = idx
    return int(best_index)


def dataframe_from_excel(path: Path, sheet_name: str | int | None = None) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name=sheet_name if sheet_name is not None else 0, header=None, dtype=object)
    header_index = detect_header_row_frame(raw, ["invoice", "order", "tax", "gst", "state", "hsn"])
    headers = unique_headers([clean_column(value) or f"column {idx}" for idx, value in enumerate(raw.iloc[header_index].tolist())])
    frame = raw.iloc[header_index + 1:].copy()
    frame.columns = headers
    return frame.dropna(how="all")


def excel_frames(path: Path) -> list[tuple[str, pd.DataFrame]]:
    sheets = pd.read_excel(path, sheet_name=None, header=None, dtype=object)
    frames: list[tuple[str, pd.DataFrame]] = []
    for sheet_name, raw in sheets.items():
        if raw.dropna(how="all").empty:
            continue
        header_index = detect_header_row_frame(raw, ["invoice", "order", "tax", "gst", "state", "hsn"])
        headers = unique_headers([clean_column(value) or f"column {idx}" for idx, value in enumerate(raw.iloc[header_index].tolist())])
        frame = raw.iloc[header_index + 1:].copy()
        frame.columns = headers
        frame = frame.dropna(how="all")
        if not frame.empty:
            frames.append((sheet_name, frame))
    return frames
