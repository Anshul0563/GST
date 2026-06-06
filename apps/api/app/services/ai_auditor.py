from __future__ import annotations

import re
from collections import Counter
from datetime import datetime
from decimal import Decimal
from typing import Any, Iterable

from app.models.entities import GSTProfile, IssueLog, NormalizedTransaction
from app.services.validation import money, validate_gstin, round_money, validate_transaction
from app.utils.states import STATE_CODES, state_code_from_text


ISSUE_SEVERITY = {
    "duplicate_invoice": "warning",
    "missing_invoice_number": "error",
    "missing_gst_rate": "error",
    "missing_pos": "error",
    "invalid_gstin": "error",
    "invalid_state_code": "error",
    "taxable_mismatch": "warning",
    "tax_split_mismatch": "warning",
    "return_mismatch": "warning",
    "credit_note_mismatch": "warning",
    "marketplace_reconciliation": "warning",
}


def normalize_invoice_no(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    normalized = re.sub(r"[^A-Za-z0-9]+", "", text).upper()
    return normalized or None


def compute_tax_total(row: NormalizedTransaction) -> Decimal:
    return round_money(money(row.igst) + money(row.cgst) + money(row.sgst) + money(row.cess))


def compute_expected_tax(row: NormalizedTransaction) -> Decimal:
    return round_money(money(row.taxable_value) * money(row.gst_rate) / Decimal("100"))


def transaction_issues(row: NormalizedTransaction, profile: GSTProfile, invoice_map: dict[str, list[NormalizedTransaction]]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    normalized_invoice = normalize_invoice_no(row.invoice_no)
    invoice_key = normalized_invoice or ""
    is_return = row.doc_type in {"credit_note", "debit_note"}
    if not row.invoice_no:
        issues.append(
            {
                "transaction_id": row.id,
                "issue_type": "missing_invoice_number",
                "description": "Missing invoice number",
                "field": "invoice_no",
                "value": None,
                "severity": ISSUE_SEVERITY["missing_invoice_number"],
            }
        )
    if row.gst_rate <= Decimal("0"):
        issues.append(
            {
                "transaction_id": row.id,
                "issue_type": "missing_gst_rate",
                "description": "Missing or zero GST rate",
                "field": "gst_rate",
                "value": str(row.gst_rate),
                "severity": ISSUE_SEVERITY["missing_gst_rate"],
            }
        )
    if not row.buyer_state_code:
        issues.append(
            {
                "transaction_id": row.id,
                "issue_type": "missing_pos",
                "description": "Missing place of supply (buyer state code)",
                "field": "buyer_state_code",
                "value": None,
                "severity": ISSUE_SEVERITY["missing_pos"],
            }
        )
    elif row.buyer_state_code not in STATE_CODES:
        issues.append(
            {
                "transaction_id": row.id,
                "issue_type": "invalid_state_code",
                "description": "Invalid POS state code",
                "field": "buyer_state_code",
                "value": str(row.buyer_state_code),
                "severity": ISSUE_SEVERITY["invalid_state_code"],
            }
        )
    if not validate_gstin(row.gstin):
        issues.append(
            {
                "transaction_id": row.id,
                "issue_type": "invalid_gstin",
                "description": "Invalid GSTIN",
                "field": "gstin",
                "value": str(row.gstin),
                "severity": ISSUE_SEVERITY["invalid_gstin"],
            }
        )
    expected_tax = compute_expected_tax(row)
    actual_tax = compute_tax_total(row)
    if abs(expected_tax - actual_tax) > Decimal("1.00"):
        issues.append(
            {
                "transaction_id": row.id,
                "issue_type": "taxable_mismatch",
                "description": "Taxable value and tax amounts do not reconcile",
                "field": "taxable_value",
                "value": f"expected {expected_tax} actual {actual_tax}",
                "severity": ISSUE_SEVERITY["taxable_mismatch"],
            }
        )
    if row.buyer_state_code and row.buyer_state_code in STATE_CODES:
        same_state = row.buyer_state_code == profile.state_code
        if same_state and money(row.igst) != Decimal("0.00"):
            issues.append(
                {
                    "transaction_id": row.id,
                    "issue_type": "tax_split_mismatch",
                    "description": "Intra-state supplies should not have IGST",
                    "field": "igst",
                    "value": str(row.igst),
                    "severity": ISSUE_SEVERITY["tax_split_mismatch"],
                }
            )
        if not same_state and (money(row.cgst) != Decimal("0.00") or money(row.sgst) != Decimal("0.00")):
            issues.append(
                {
                    "transaction_id": row.id,
                    "issue_type": "tax_split_mismatch",
                    "description": "Inter-state supplies should not contain CGST/SGST",
                    "field": "cgst/sgst",
                    "value": f"{row.cgst}/{row.sgst}",
                    "severity": ISSUE_SEVERITY["tax_split_mismatch"],
                }
            )
    if is_return:
        matches = invoice_map.get(invoice_key, []) if invoice_key else []
        if not matches:
            issues.append(
                {
                    "transaction_id": row.id,
                    "issue_type": "return_mismatch",
                    "description": "Return or credit note without a matching invoice",
                    "field": "invoice_no",
                    "value": row.invoice_no,
                    "severity": ISSUE_SEVERITY["return_mismatch"],
                }
            )
        else:
            issues.append(
                {
                    "transaction_id": row.id,
                    "issue_type": "credit_note_mismatch",
                    "description": "Return document may not align with original invoice amount",
                    "field": "gross_amount",
                    "value": str(row.gross_amount),
                    "severity": ISSUE_SEVERITY["credit_note_mismatch"],
                }
            )
    if row.validation_status != "valid":
        issues.append(
            {
                "transaction_id": row.id,
                "issue_type": "marketplace_reconciliation",
                "description": "Imported row has validation issues from marketplace parsing",
                "field": "validation_status",
                "value": row.validation_status,
                "severity": ISSUE_SEVERITY["marketplace_reconciliation"],
            }
        )
    if invoice_key and len(invoice_map.get(invoice_key, [])) > 1:
        issues.append(
            {
                "transaction_id": row.id,
                "issue_type": "duplicate_invoice",
                "description": "Duplicate invoice detected for the same GSTIN, platform and period",
                "field": "invoice_no",
                "value": row.invoice_no,
                "severity": ISSUE_SEVERITY["duplicate_invoice"],
            }
        )
    return issues


def compute_audit_details(rows: Iterable[NormalizedTransaction], profile: GSTProfile) -> tuple[dict[str, int], list[dict[str, Any]]]:
    invoice_map: dict[str, list[NormalizedTransaction]] = {}
    for row in rows:
        key = normalize_invoice_no(row.invoice_no) or f"missing-{row.id}"
        invoice_map.setdefault(key, []).append(row)
    issues: list[dict[str, Any]] = []
    counters: Counter[str] = Counter()
    for row in rows:
        row_issues = transaction_issues(row, profile, invoice_map)
        for issue in row_issues:
            counters[issue["issue_type"]] += 1
        issues.extend(row_issues)
    return dict(counters), issues


def audit_risk_score(issue_counts: dict[str, int], pending_errors: int) -> int:
    score = 100
    score -= issue_counts.get("duplicate_invoice", 0) * 5
    score -= issue_counts.get("missing_invoice_number", 0) * 8
    score -= issue_counts.get("missing_pos", 0) * 10
    score -= issue_counts.get("missing_gst_rate", 0) * 10
    score -= issue_counts.get("invalid_gstin", 0) * 10
    score -= issue_counts.get("taxable_mismatch", 0) * 6
    score -= issue_counts.get("tax_split_mismatch", 0) * 6
    score -= issue_counts.get("return_mismatch", 0) * 4
    score -= issue_counts.get("marketplace_reconciliation", 0) * 3
    score -= pending_errors * 2
    return max(0, min(100, score))


def build_audit_warnings(issue_counts: dict[str, int]) -> list[str]:
    warnings: list[str] = []
    if issue_counts.get("duplicate_invoice"):
        warnings.append(f"{issue_counts['duplicate_invoice']} Duplicate Invoices")
    if issue_counts.get("missing_pos"):
        warnings.append(f"{issue_counts['missing_pos']} POS Issues")
    if issue_counts.get("return_mismatch"):
        warnings.append(f"{issue_counts['return_mismatch']} Return Mismatches")
    if issue_counts.get("missing_invoice_number"):
        warnings.append(f"{issue_counts['missing_invoice_number']} Missing Invoice Numbers")
    if issue_counts.get("missing_gst_rate"):
        warnings.append(f"{issue_counts['missing_gst_rate']} GST Rate Issues")
    return warnings


def compute_readiness_status(issue_counts: dict[str, int], pending_errors: int) -> str:
    total_issues = sum(issue_counts.values()) + pending_errors
    if total_issues == 0:
        return "Ready To File"
    if total_issues <= 5:
        return "Almost Ready"
    return "Needs Attention"


def format_audit_row(row: NormalizedTransaction, issue: dict[str, Any]) -> dict[str, Any]:
    return {
        "transaction_id": issue.get("transaction_id"),
        "issue_type": issue.get("issue_type"),
        "platform": row.platform,
        "invoice_no": row.invoice_no,
        "invoice_date": row.invoice_date.isoformat() if row.invoice_date else None,
        "field": issue.get("field"),
        "description": issue.get("description"),
        "severity": issue.get("severity"),
    }


def build_audit_summary(rows: Iterable[NormalizedTransaction], profile: GSTProfile) -> dict[str, Any]:
    row_list = list(rows)
    issue_counts, issues = compute_audit_details(row_list, profile)
    pending_errors = sum(1 for row in row_list if row.validation_status in {"error", "invalid"})
    score = audit_risk_score(issue_counts, pending_errors)
    row_map = {row.id: row for row in row_list}
    return {
        "auditor_health_score": score,
        "auditor_risk_score": 100 - score,
        "readiness_status": compute_readiness_status(issue_counts, pending_errors),
        "issue_counts": issue_counts,
        "warnings": build_audit_warnings(issue_counts),
        "details": [
            format_audit_row(row_map.get(issue.get("transaction_id"), row_list[0]), issue)
            for issue in issues
        ],
    }


def refresh_validation_status(row: NormalizedTransaction) -> None:
    txn = {
        "platform": row.platform,
        "gstin": row.gstin,
        "filing_period": row.filing_period,
        "doc_type": row.doc_type,
        "buyer_state_code": row.buyer_state_code,
        "invoice_no": row.invoice_no,
        "gst_rate": row.gst_rate,
        "etin": row.etin,
        "taxable_value": row.taxable_value,
        "igst": row.igst,
        "cgst": row.cgst,
        "sgst": row.sgst,
        "cess": row.cess,
    }
    errors = validate_transaction(txn)
    row.validation_status = "skipped" if errors and all(
        error in {"Zero amount row", "Zero rate and zero taxable row"} for error in errors
    ) else "invalid" if errors else "valid"
    row.validation_errors = "; ".join(errors) if errors else None


def create_issue_log(
    user_id: int,
    profile_id: int,
    row: NormalizedTransaction,
    issue_type: str,
    field: str | None,
    before_value: object,
    after_value: object,
    reason: str,
) -> IssueLog:
    return IssueLog(
        user_id=user_id,
        profile_id=profile_id,
        transaction_id=row.id,
        issue_type=issue_type,
        field=field,
        before_value=str(before_value) if before_value is not None else None,
        after_value=str(after_value) if after_value is not None else None,
        reason=reason,
        created_at=datetime.utcnow(),
    )


def fix_detected_issues(rows: Iterable[NormalizedTransaction], profile: GSTProfile, user_id: int, db) -> list[IssueLog]:
    logs: list[IssueLog] = []
    row_list = list(rows)
    for row in row_list:
        original = {
            "buyer_state_code": row.buyer_state_code,
            "invoice_no": row.invoice_no,
            "gst_rate": row.gst_rate,
            "igst": row.igst,
            "cgst": row.cgst,
            "sgst": row.sgst,
            "validation_status": row.validation_status,
            "validation_errors": row.validation_errors,
        }
        if not row.buyer_state_code and row.buyer_state_name:
            fixed_state = state_code_from_text(row.buyer_state_name)
            if fixed_state and fixed_state != row.buyer_state_code:
                row.buyer_state_code = fixed_state
                logs.append(create_issue_log(user_id, profile.id, row, "missing_pos", "buyer_state_code", original["buyer_state_code"], fixed_state, "Filled POS from buyer state name"))
        if row.buyer_state_code and row.buyer_state_code not in STATE_CODES and row.buyer_state_name:
            fixed_state = state_code_from_text(row.buyer_state_name)
            if fixed_state and fixed_state != row.buyer_state_code:
                row.buyer_state_code = fixed_state
                logs.append(create_issue_log(user_id, profile.id, row, "invalid_state_code", "buyer_state_code", original["buyer_state_code"], fixed_state, "Resolved invalid POS from buyer state name"))
        if not row.invoice_no and row.order_id:
            fixed_invoice_no = str(row.order_id).strip()
            if fixed_invoice_no:
                row.invoice_no = fixed_invoice_no
                logs.append(create_issue_log(user_id, profile.id, row, "missing_invoice_number", "invoice_no", original["invoice_no"], fixed_invoice_no, "Backfilled missing invoice number from order id"))
        rounded_rate = round_money(row.gst_rate)
        if rounded_rate != row.gst_rate:
            row.gst_rate = rounded_rate
            logs.append(create_issue_log(user_id, profile.id, row, "gst_rate_rounding", "gst_rate", original["gst_rate"], rounded_rate, "Rounded GST rate to standard precision"))
        expected_tax = compute_expected_tax(row)
        actual_tax = compute_tax_total(row)
        if abs(expected_tax - actual_tax) > Decimal("0.25"):
            if row.buyer_state_code == profile.state_code:
                row.igst = Decimal("0.00")
                row.cgst = round_money(expected_tax / 2)
                row.sgst = round_money(expected_tax / 2)
            else:
                row.igst = expected_tax
                row.cgst = Decimal("0.00")
                row.sgst = Decimal("0.00")
            logs.append(create_issue_log(user_id, profile.id, row, "tax_rounding", "igst/cgst/sgst", f"{original['igst']}/{original['cgst']}/{original['sgst']}", f"{row.igst}/{row.cgst}/{row.sgst}", "Recalculated taxes from taxable value and GST rate"))
        if row.validation_status != "valid":
            refresh_validation_status(row)
            logs.append(create_issue_log(user_id, profile.id, row, "revalidation", "validation_status", original["validation_status"], row.validation_status, "Revalidated transaction after automated corrections"))
        if row.validation_errors != original["validation_errors"]:
            logs.append(create_issue_log(user_id, profile.id, row, "revalidation_error", "validation_errors", original["validation_errors"], row.validation_errors, "Updated validation errors after automated corrections"))
        if logs:
            db.add(row)
    return logs


def detect_marketplace(file_contents: str) -> tuple[str, int]:
    normalized = file_contents.lower()
    if "seller gstin" in normalized and "invoice number" in normalized and "igst rate" in normalized:
        return "amazon", 92
    if "order id" in normalized and "invoice no" in normalized and "taxable value" in normalized:
        return "flipkart", 90
    if "tax_invoice_details" in normalized or "tcs_sales" in normalized:
        return "meesho", 90
    if "snapdeal" in normalized or "seller gstin" in normalized and "tax" in normalized and "invoice date" in normalized:
        return "snapdeal", 82
    if "blinkit" in normalized or "grocery" in normalized and "invoice" in normalized:
        return "blinkit", 78
    return "custom", 45
