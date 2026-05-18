from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import pandas as pd

from app.services.excel_export import safe_excel_value
from app.services.validation import money, validate_gstin


FIELD_ALIASES = {
    "supplier_gstin": ["supplier gstin", "ctin", "gstin", "gstin of supplier", "supplier_gst"],
    "invoice_no": ["invoice number", "invoice no", "inum", "inv no", "bill no", "voucher no", "document number"],
    "invoice_date": ["invoice date", "idt", "inv date", "bill date", "voucher date", "date"],
    "taxable_value": ["taxable value", "txval", "taxable", "taxable amount", "assessable value"],
    "igst": ["igst", "integrated tax", "integrated tax amount", "iamt"],
    "cgst": ["cgst", "central tax", "central tax amount", "camt"],
    "sgst": ["sgst", "state tax", "state/ut tax", "state tax amount", "samt"],
}

CATEGORIES = ["matched", "partially_matched", "invoice_mismatch", "tax_mismatch", "gstin_mismatch", "missing_in_books", "missing_in_portal", "duplicate_invoice", "invalid_gstin"]


@dataclass
class ReconSettings:
    tax_tolerance: Decimal = Decimal("1.00")
    date_tolerance_days: int = 3
    enable_date_tolerance: bool = True
    enable_fuzzy_invoice: bool = True


def clean_header(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower().replace("_", " "))


def normalize_invoice(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").strip().lower())


def to_date(value: object) -> date | None:
    parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        return None
    return parsed.date()


def read_any_table(path: Path) -> pd.DataFrame:
    suffix = path.suffix.lower()
    frames: list[pd.DataFrame] = []
    if suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            for key in ("b2b", "cdnr", "data", "rows", "invoices"):
                if isinstance(data.get(key), list):
                    frames.append(pd.json_normalize(data[key]))
        elif isinstance(data, list):
            frames.append(pd.json_normalize(data))
    elif suffix == ".csv":
        frames.append(pd.read_csv(path, dtype=str))
    else:
        sheets = pd.read_excel(path, sheet_name=None, dtype=str, header=None)
        for sheet in sheets.values():
            header_idx = detect_header_row(sheet)
            if header_idx is None:
                continue
            header = sheet.iloc[header_idx].fillna("").map(str).tolist()
            frame = sheet.iloc[header_idx + 1:].copy()
            frame.columns = header
            frames.append(frame)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True).dropna(how="all")


def detect_header_row(frame: pd.DataFrame) -> int | None:
    alias_words = {alias for values in FIELD_ALIASES.values() for alias in values}
    for idx, row in frame.head(40).iterrows():
        cleaned = {clean_header(value) for value in row.tolist()}
        score = sum(1 for value in cleaned if value in alias_words)
        if score >= 2:
            return int(idx)
    return 0 if len(frame) else None


def find_column(columns: list[str], key: str) -> str | None:
    cleaned = {clean_header(column): column for column in columns}
    for alias in FIELD_ALIASES[key]:
        if alias in cleaned:
            return cleaned[alias]
    for column in columns:
        normalized = clean_header(column)
        if any(alias in normalized for alias in FIELD_ALIASES[key]):
            return column
    return None


def normalize_rows(path: Path, source: str) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    frame = read_any_table(path)
    errors: list[dict[str, Any]] = []
    rows: list[dict[str, Any]] = []
    if frame.empty:
        return rows, [{"source": source, "file": path.name, "error": "No tabular rows found"}]
    columns = [str(column) for column in frame.columns]
    mapping = {key: find_column(columns, key) for key in FIELD_ALIASES}
    for required in ("supplier_gstin", "invoice_no", "taxable_value"):
        if not mapping.get(required):
            errors.append({"source": source, "file": path.name, "error": f"Missing required column: {required}"})
    for index, record in frame.iterrows():
        row = {key: record.get(column) if column else None for key, column in mapping.items()}
        supplier = str(row.get("supplier_gstin") or "").strip().upper()
        invoice_no = str(row.get("invoice_no") or "").strip()
        if not supplier and not invoice_no:
            continue
        normalized = {
            "source": source,
            "row_no": int(index) + 1,
            "supplier_gstin": supplier,
            "invoice_no": invoice_no,
            "invoice_key": normalize_invoice(invoice_no),
            "invoice_date": to_date(row.get("invoice_date")),
            "taxable_value": money(row.get("taxable_value")),
            "igst": money(row.get("igst")),
            "cgst": money(row.get("cgst")),
            "sgst": money(row.get("sgst")),
        }
        normalized["total_tax"] = normalized["igst"] + normalized["cgst"] + normalized["sgst"]
        normalized["raw"] = {str(key): safe_excel_value(value) for key, value in record.to_dict().items()}
        if supplier and not validate_gstin(supplier):
            normalized["invalid_gstin"] = True
        rows.append(normalized)
    return rows, errors


def row_key(row: dict[str, Any]) -> tuple[str, str]:
    return str(row.get("supplier_gstin") or ""), str(row.get("invoice_key") or "")


def amount_delta(book: dict[str, Any] | None, portal: dict[str, Any] | None) -> Decimal:
    book_tax = money(book.get("total_tax") if book else 0)
    portal_tax = money(portal.get("total_tax") if portal else 0)
    return book_tax - portal_tax


def classify_pair(book: dict[str, Any] | None, portal: dict[str, Any] | None, settings: ReconSettings, score: Decimal = Decimal("100")) -> dict[str, Any]:
    source = book or portal or {}
    delta = amount_delta(book, portal)
    taxable_delta = money((book or {}).get("taxable_value")) - money((portal or {}).get("taxable_value"))
    if book and portal:
        date_ok = True
        if settings.enable_date_tolerance and book.get("invoice_date") and portal.get("invoice_date"):
            date_ok = abs((book["invoice_date"] - portal["invoice_date"]).days) <= settings.date_tolerance_days
        if abs(delta) <= settings.tax_tolerance and abs(taxable_delta) <= settings.tax_tolerance and date_ok:
            category = "matched" if score >= Decimal("100") else "partially_matched"
            reason = "Exact match" if category == "matched" else "Fuzzy invoice/date tolerance match"
        elif abs(delta) > settings.tax_tolerance or abs(taxable_delta) > settings.tax_tolerance:
            category = "tax_mismatch"
            reason = f"Tax/taxable difference exceeds Rs {settings.tax_tolerance}"
        else:
            category = "partially_matched"
            reason = "Date or invoice differs within candidate match"
    elif book:
        category = "missing_in_portal"
        reason = "Invoice exists in books but not in portal 2A/2B"
    else:
        category = "missing_in_books"
        reason = "Invoice exists in portal 2A/2B but not in books"
    if source.get("invalid_gstin"):
        category = "invalid_gstin"
        reason = "Supplier GSTIN is invalid"
    return {
        "supplier_gstin": source.get("supplier_gstin"),
        "invoice_no": source.get("invoice_no"),
        "invoice_date": source.get("invoice_date"),
        "taxable_value": money(source.get("taxable_value")),
        "igst": money(source.get("igst")),
        "cgst": money(source.get("cgst")),
        "sgst": money(source.get("sgst")),
        "total_tax": money(source.get("total_tax")),
        "tax_difference": delta,
        "match_score": score,
        "category": category,
        "mismatch_reason": reason,
        "books_json": json.dumps(book, default=str) if book else None,
        "portal_json": json.dumps(portal, default=str) if portal else None,
    }


def find_fuzzy_match(book: dict[str, Any], portal_rows: list[dict[str, Any]], used: set[int], settings: ReconSettings) -> tuple[int | None, Decimal]:
    if not settings.enable_fuzzy_invoice:
        return None, Decimal("0")
    best_idx: int | None = None
    best_score = Decimal("0")
    for idx, portal in enumerate(portal_rows):
        if idx in used:
            continue
        if portal.get("supplier_gstin") != book.get("supplier_gstin"):
            continue
        ratio = Decimal(str(SequenceMatcher(None, str(book.get("invoice_key")), str(portal.get("invoice_key"))).ratio() * 100)).quantize(Decimal("0.01"))
        tax_ok = abs(amount_delta(book, portal)) <= settings.tax_tolerance
        date_ok = True
        if settings.enable_date_tolerance and book.get("invoice_date") and portal.get("invoice_date"):
            date_ok = abs((book["invoice_date"] - portal["invoice_date"]).days) <= settings.date_tolerance_days
        if ratio >= Decimal("82") and tax_ok and date_ok and ratio > best_score:
            best_idx = idx
            best_score = ratio
    return best_idx, best_score


def reconcile(book_rows: list[dict[str, Any]], portal_rows: list[dict[str, Any]], settings: ReconSettings) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    results: list[dict[str, Any]] = []
    used_portal: set[int] = set()
    seen_books: set[tuple[str, str]] = set()
    portal_by_key: dict[tuple[str, str], list[tuple[int, dict[str, Any]]]] = {}
    for idx, portal in enumerate(portal_rows):
        portal_by_key.setdefault(row_key(portal), []).append((idx, portal))
    for book in book_rows:
        key = row_key(book)
        if key in seen_books:
            results.append({**classify_pair(book, None, settings), "category": "duplicate_invoice", "mismatch_reason": "Duplicate invoice in books"})
            continue
        seen_books.add(key)
        candidates = portal_by_key.get(key, [])
        match = next(((idx, row) for idx, row in candidates if idx not in used_portal), None)
        if match:
            idx, portal = match
            used_portal.add(idx)
            results.append(classify_pair(book, portal, settings))
            continue
        fuzzy_idx, score = find_fuzzy_match(book, portal_rows, used_portal, settings)
        if fuzzy_idx is not None:
            used_portal.add(fuzzy_idx)
            results.append(classify_pair(book, portal_rows[fuzzy_idx], settings, score))
            continue
        results.append(classify_pair(book, None, settings))
    seen_portal: set[tuple[str, str]] = set()
    for idx, portal in enumerate(portal_rows):
        if idx in used_portal:
            continue
        key = row_key(portal)
        if key in seen_portal:
            results.append({**classify_pair(None, portal, settings), "category": "duplicate_invoice", "mismatch_reason": "Duplicate invoice in portal"})
        else:
            results.append(classify_pair(None, portal, settings))
        seen_portal.add(key)
    counts = {category: 0 for category in CATEGORIES}
    for row in results:
        counts[row["category"]] = counts.get(row["category"], 0) + 1
    matched = counts.get("matched", 0)
    mismatches = len(results) - matched
    risk = sum((abs(money(row["total_tax"])) for row in results if row["category"] in {"missing_in_portal", "tax_mismatch", "invalid_gstin"}), Decimal("0.00"))
    tax_difference = sum((money(row["tax_difference"]) for row in results), Decimal("0.00"))
    summary = {
        **counts,
        "total_portal_invoices": len(portal_rows),
        "total_book_invoices": len(book_rows),
        "total_rows": len(results),
        "matched_percent": round((matched / len(results) * 100) if results else 0, 2),
        "mismatch_percent": round((mismatches / len(results) * 100) if results else 0, 2),
        "tax_difference": money(tax_difference),
        "itc_risk_amount": money(risk),
    }
    return results, summary


def write_reconciliation_excel(path: Path, results: list[dict[str, Any]], summary: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        pd.DataFrame([summary]).to_excel(writer, sheet_name="Summary", index=False)
        all_rows = pd.DataFrame([{key: safe_excel_value(value) for key, value in row.items() if key not in {"books_json", "portal_json"}} for row in results])
        all_rows.to_excel(writer, sheet_name="All Results", index=False)
        for category in CATEGORIES:
            filtered = all_rows[all_rows["category"] == category] if not all_rows.empty and "category" in all_rows else pd.DataFrame()
            filtered.to_excel(writer, sheet_name=category[:31], index=False)
    return path
