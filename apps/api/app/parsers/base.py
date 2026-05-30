from dataclasses import dataclass, field
from pathlib import Path
import json
import re
from typing import Any

import pandas as pd

from app.services.pos_resolver import apply_pos_resolution
from app.services.transaction_normalizer import finalize_transaction
from app.services.validation import money


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
    debug: dict = field(default_factory=dict)


class MarketplaceParser:
    platform = "custom"

    def __init__(self, gstin: str, filing_period: str):
        self.gstin = gstin.upper()
        self.filing_period = filing_period

    def parse(self, files: list[Path]) -> ParseResult:
        raise NotImplementedError

    def normalize_row(self, row: dict[str, Any], source_file: str) -> dict:
        raw_invoice_date = first_value(
            row,
            [
                "invoice_date",
                "invoice date",
                "buyer invoice date",
                "invoice generated date",
                "shipment date",
                "order date",
                "date",
            ],
        )

        doc_type = str(
            first_value(
                row,
                ["doc_type", "document type", "transaction type", "type"],
            )
            or "invoice"
        ).lower()

        if "refund" in doc_type or "return" in doc_type or "credit" in doc_type:
            doc_type = "credit_note"
        elif "debit" in doc_type:
            doc_type = "debit_note"
        else:
            doc_type = "invoice"

        if doc_type == "credit_note":
            raw_document_date = first_value(
                row,
                [
                    "credit_note_date",
                    "credit note date",
                    "cancel return date",
                    "return date",
                    "document date",
                    "doc date",
                    "invoice_date",
                    "invoice date",
                    "buyer invoice date",
                    "order date",
                ],
            )
        elif doc_type == "debit_note":
            raw_document_date = first_value(
                row,
                [
                    "debit_note_date",
                    "debit note date",
                    "document date",
                    "doc date",
                    "invoice_date",
                    "invoice date",
                    "buyer invoice date",
                    "order date",
                ],
            )
        else:
            raw_document_date = raw_invoice_date

        document_date = parse_date(raw_document_date)

        txn = {
            "platform": self.platform,
            "gstin": self.gstin,
            "etin": first_value(row, ["etin", "ecommerce gstin", "operator gstin"])
            or ETINS.get(self.platform),
            "filing_period": self.filing_period,
            "order_id": text(
                first_value(
                    row,
                    [
                        "order_id",
                        "order id",
                        "amazon order id",
                        "order no",
                        "sub order num",
                        "suborder no",
                        "suborder number",
                    ],
                )
            ),
            "order_item_id": text(
                first_value(
                    row,
                    [
                        "order_item_id",
                        "order item id",
                        "order item identifier",
                        "item id",
                        "sub order num",
                        "suborder no",
                        "suborder number",
                    ],
                )
            ),
            "invoice_no": text(
                first_value(
                    row,
                    [
                        "invoice_no",
                        "invoice number",
                        "invoice id",
                        "invoice no",
                        "tax invoice no",
                        "credit note id/ debit note id",
                        "credit note id",
                        "debit note id",
                        "document number",
                        "document no",
                        "doc no",
                        "voucher no",
                    ],
                )
            ),
            "invoice_date": parse_date(raw_invoice_date),
            "document_date": document_date,
            "doc_type": doc_type,
            "buyer_state_code": text(
                first_value(row, ["buyer_state_code", "state code", "gst state code"])
            ),
            "buyer_state_name": text(
                first_value(row, ["buyer_state_name", "state name", "gst state"])
            ),
            "hsn": text(first_value(row, ["hsn", "hsn code", "hsn/sac"])),
            "product_name": text(
                first_value(
                    row,
                    [
                        "product_name",
                        "product title",
                        "product name",
                        "sku title",
                        "item description",
                    ],
                )
            ),
            "sku": text(first_value(row, ["sku", "seller sku", "fsn", "merchant sku"])),
            "qty": money(first_value(row, ["qty", "quantity", "item quantity"])),
            "taxable_value": money(
                first_value(
                    row,
                    [
                        "taxable_value",
                        "taxable value",
                        "taxable amount",
                        "tax exclusive gross",
                        "taxable sales",
                        "price before tax",
                        "taxable turnover",
                        "total taxable sale value",
                    ],
                )
            ),
            "gst_rate": money(
                first_tax_value(
                    row,
                    ["gst_rate", "gst rate", "tax rate", "igst rate", "total tax rate"],
                )
            ),
            "igst": money(
                first_tax_value(
                    row,
                    [
                        "igst tax",
                        "igst amount",
                        "integrated tax",
                        "igst",
                        "tax amount",
                        "total tax amount",
                        "gst amount",
                    ],
                )
            ),
            "cgst": money(
                first_tax_value(row, ["cgst tax", "cgst amount", "central tax", "cgst"])
            ),
            "sgst": money(
                first_tax_value(row, ["sgst tax", "sgst amount", "state tax", "sgst"])
            ),
            "cess": money(first_value(row, ["cess", "cess amount"])),
            "tcs": money(
                first_value(
                    row,
                    [
                        "total tcs deducted",
                        "tcs amount",
                        "tcs igst amount",
                        "tcs cgst amount",
                        "tcs sgst amount",
                        "tcs",
                    ],
                )
            ),
            "tds": money(
                first_value(
                    row,
                    [
                        "tds amount",
                        "tds igst amount",
                        "tds cgst amount",
                        "tds sgst amount",
                        "tds",
                    ],
                )
            ),
            "gross_amount": money(
                first_value(
                    row,
                    [
                        "gross_amount",
                        "gross amount",
                        "invoice amount",
                        "total amount",
                        "selling price",
                        "price before discount",
                        "total invoice value",
                    ],
                )
            ),
            "discount_seller": money(
                first_value(row, ["discount_seller", "seller discount", "merchant discount"])
            ),
            "discount_platform": money(
                first_value(row, ["discount_platform", "platform discount", "bank discount", "cashback"])
            ),
            "settlement_amount": money(
                first_value(row, ["settlement_amount", "settlement amount", "net payable"])
            ),
            "source_file": source_file,
            "raw_row_json": json.dumps(row, default=str),
        }

        apply_pos_resolution(row, txn, self.platform)
        return txn


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


def belongs_to_period(value: object, filing_period: str) -> bool:
    """
    Checks whether a parsed document date belongs to filing_period.

    filing_period format:
    - 022026
    - 032026
    - 042026

    Important:
    Use document_date, not invoice_date, because credit notes / debit notes
    may belong to a different period than the original invoice.
    """
    if value in (None, ""):
        return False

    parsed = parse_date(value) if not hasattr(value, "month") else value

    if parsed is None:
        return False

    month = int(str(filing_period)[:2])
    year = int(str(filing_period)[2:])

    return parsed.month == month and parsed.year == year


def should_skip_transaction(txn: dict[str, Any]) -> bool:
    if txn.get("invoice_no"):
        return False

    amount_fields = ("taxable_value", "gross_amount", "igst", "cgst", "sgst", "cess")
    return all(money(txn.get(field)) == 0 for field in amount_fields)


def record_period_exclusion(
    result: ParseResult,
    *,
    source_file: str,
    row_number: int,
    txn: dict[str, Any],
    sheet_name: str | None = None,
    reason: str = "document date outside filing period",
) -> None:
    entry = {
        "file": source_file,
        "row": row_number,
        "invoice_no": txn.get("invoice_no"),
        "doc_type": txn.get("doc_type"),
        "document_date": str(txn.get("document_date")),
        "taxable_value": str(txn.get("taxable_value")),
        "reason": reason,
    }
    if sheet_name is not None:
        entry["sheet"] = sheet_name
    result.debug.setdefault("period_excluded_rows", []).append(entry)


def finalize_period_transaction(
    result: ParseResult,
    txn: dict[str, Any],
    *,
    source_file: str,
    row_number: int,
    sheet_name: str | None = None,
) -> dict[str, Any] | None:
    finalized = finalize_transaction(txn)
    if belongs_to_period(finalized.get("document_date"), finalized.get("filing_period")):
        return finalized

    record_period_exclusion(
        result,
        source_file=source_file,
        sheet_name=sheet_name,
        row_number=row_number,
        txn=finalized,
    )
    return None


def has_explicit_tax_split(row: dict[str, Any]) -> bool:
    keys = {clean_column(key) for key in row.keys()}
    split_markers = (
        "igst amount",
        "igst tax",
        "integrated tax",
        "cgst amount",
        "cgst tax",
        "central tax",
        "sgst amount",
        "sgst tax",
        "state tax",
        "utgst",
    )
    return any(
        any(marker in key for marker in split_markers)
        for key in keys
        if not is_collection_column(key)
    )


def first_value(row: dict[str, Any], candidates: list[str]) -> Any:
    lowered = {clean_column(k): v for k, v in row.items()}

    for candidate in candidates:
        cleaned_candidate = clean_column(candidate)
        if cleaned_candidate in lowered and lowered[cleaned_candidate] not in (None, ""):
            return lowered[cleaned_candidate]

    for candidate in candidates:
        cleaned_candidate = clean_column(candidate)
        if len(cleaned_candidate) <= 3:
            continue

        for key, value in lowered.items():
            if cleaned_candidate in key and value not in (None, ""):
                return value

    return None


def is_collection_column(key: str) -> bool:
    tokens = set(clean_column(key).split())
    return bool(tokens.intersection({"tcs", "tds"}))


def first_tax_value(row: dict[str, Any], candidates: list[str]) -> Any:
    return first_value(
        {
            key: value
            for key, value in row.items()
            if not is_collection_column(str(key))
        },
        candidates,
    )


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

        non_empty = sum(
            1
            for value in row.tolist()
            if str(value).strip() and str(value).lower() != "nan"
        )

        score += min(non_empty, 8) / 20

        if score > best_score:
            best_score = score
            best_index = idx

    return int(best_index)


def dataframe_from_excel(
    path: Path,
    sheet_name: str | int | None = None,
) -> pd.DataFrame:
    raw = pd.read_excel(
        path,
        sheet_name=sheet_name if sheet_name is not None else 0,
        header=None,
        dtype=object,
    )

    header_index = detect_header_row_frame(
        raw,
        ["invoice", "order", "tax", "gst", "state", "hsn"],
    )

    headers = unique_headers(
        [
            clean_column(value) or f"column {idx}"
            for idx, value in enumerate(raw.iloc[header_index].tolist())
        ]
    )

    frame = raw.iloc[header_index + 1:].copy()
    frame.columns = headers

    return frame.dropna(how="all")


def dataframe_from_path(path: Path) -> pd.DataFrame:
    if path.suffix.lower() == ".csv":
        frame = pd.read_csv(path, dtype=object, encoding_errors="ignore")
        frame.columns = [clean_column(col) for col in frame.columns]
        return frame.dropna(how="all")
    return dataframe_from_excel(path)


def raw_frames(path: Path) -> list[tuple[str, pd.DataFrame]]:
    if path.suffix.lower() == ".csv":
        frame = pd.read_csv(path, header=None, dtype=object, encoding_errors="ignore")
        return [(path.stem, frame)]

    sheets = pd.read_excel(path, sheet_name=None, header=None, dtype=object)
    return [(str(sheet_name), frame) for sheet_name, frame in sheets.items()]


def excel_frames(path: Path) -> list[tuple[str, pd.DataFrame]]:
    if path.suffix.lower() == ".csv":
        frame = dataframe_from_path(path)
        if frame.empty:
            return []
        return [(path.stem, frame)]

    sheets = pd.read_excel(path, sheet_name=None, header=None, dtype=object)
    frames: list[tuple[str, pd.DataFrame]] = []

    for sheet_name, raw in sheets.items():
        if raw.dropna(how="all").empty:
            continue

        header_index = detect_header_row_frame(
            raw,
            ["invoice", "order", "tax", "gst", "state", "hsn"],
        )

        headers = unique_headers(
            [
                clean_column(value) or f"column {idx}"
                for idx, value in enumerate(raw.iloc[header_index].tolist())
            ]
        )

        frame = raw.iloc[header_index + 1:].copy()
        frame.columns = headers
        frame = frame.dropna(how="all")

        if not frame.empty:
            frames.append((sheet_name, frame))

    return frames
