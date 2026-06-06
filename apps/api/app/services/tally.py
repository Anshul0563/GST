from decimal import Decimal
from html import escape
import json
from pathlib import Path

import pandas as pd

from app.services.excel_export import safe_excel_value
from app.services.validation import money


DEFAULT_LEDGERS = {
    "sales_ledger": "Online Sales",
    "igst_ledger": "Output IGST",
    "cgst_ledger": "Output CGST",
    "sgst_ledger": "Output SGST",
    "tcs_ledger": "TCS Receivable",
    "tds_ledger": "TDS Receivable",
    "discount_ledger": "Discount Allowed",
    "round_off_ledger": "Round Off",
    "shipping_ledger": "Shipping Charges",
    "party_ledger": "eCommerce Debtors",
    "stock_item": "Marketplace Item",
    "uqc": "NOS",
}


def ledger_xml(name: str, parent: str = "Sundry Debtors") -> str:
    escaped = escape(name)
    return f"<LEDGER NAME=\"{escaped}\" RESERVEDNAME=\"\"><NAME>{escaped}</NAME><PARENT>{escape(parent)}</PARENT><ISBILLWISEON>Yes</ISBILLWISEON></LEDGER>"


def stock_item_xml(name: str, uqc: str) -> str:
    escaped = escape(name)
    return f"<STOCKITEM NAME=\"{escaped}\" RESERVEDNAME=\"\"><NAME>{escaped}</NAME><BASEUNITS>{escape(uqc)}</BASEUNITS></STOCKITEM>"


def voucher_type(doc_type: str) -> str:
    normalized = str(doc_type or "").lower()
    if normalized in {"crn", "credit", "credit_note"} or "credit" in normalized or "return" in normalized:
        return "Credit Note"
    if normalized in {"dbn", "debit", "debit_note"} or "debit" in normalized:
        return "Debit Note"
    return "Sales"


def voucher_key(row: dict) -> tuple[str, str, str, str]:
    return (
        str(row.get("platform") or "").strip().lower(),
        str(row.get("gstin") or "").strip().upper(),
        str(row.get("etin") or row.get("buyer_state_code") or "").strip().upper(),
        str(row.get("invoice_no") or row.get("order_id") or "NA").strip(),
    )


def display_voucher_no(row: dict, fallback_index: int) -> str:
    raw = str(row.get("invoice_no") or row.get("order_id") or "").strip()
    if raw:
        return raw
    return f"GB-{fallback_index:05d}"


def build_vouchers(rows: list[dict], mapping: dict[str, str] | None = None) -> list[dict]:
    ledgers = {**DEFAULT_LEDGERS, **(mapping or {})}
    vouchers: list[dict] = []
    seen: set[tuple[str, str, str, str]] = set()
    for index, row in enumerate(rows, start=1):
        key = voucher_key(row)
        if key in seen:
            continue
        seen.add(key)
        voucher_no = display_voucher_no(row, index)
        tax = money(row.get("igst")) + money(row.get("cgst")) + money(row.get("sgst"))
        taxable = money(row.get("taxable_value"))
        amount = money(row.get("gross_amount")) or taxable + tax
        vouchers.append({
            "voucher_no": voucher_no,
            "voucher_type": voucher_type(row.get("doc_type")),
            "date": row.get("invoice_date"),
            "party_ledger": ledgers["party_ledger"],
            "sales_ledger": ledgers["sales_ledger"],
            "stock_item": row.get("product_name") or row.get("sku") or ledgers["stock_item"],
            "uqc": ledgers["uqc"],
            "qty": money(row.get("qty")),
            "taxable_value": taxable,
            "igst": money(row.get("igst")),
            "cgst": money(row.get("cgst")),
            "sgst": money(row.get("sgst")),
            "tcs": money(row.get("tcs")),
            "tds": money(row.get("tds")),
            "discount": money(row.get("discount_seller")) + money(row.get("discount_platform")),
            "total_tax": tax,
            "amount": amount,
            "source": row,
        })
    return vouchers


def signed_amount(value: object, voucher_type_name: str, debit_side: bool = False) -> Decimal:
    amount = abs(money(value))
    if voucher_type_name == "Credit Note":
        return amount if debit_side else -amount
    return -amount if debit_side else amount


def build_tally_xml(company_name: str, rows: list[dict], mapping: dict[str, str] | None = None, auto_create_ledgers: bool = True) -> str:
    ledgers = {**DEFAULT_LEDGERS, **(mapping or {})}
    vouchers = build_vouchers(rows, mapping)
    entries: list[str] = []
    if auto_create_ledgers:
        parent_map = {
            "sales_ledger": "Sales Accounts",
            "igst_ledger": "Duties & Taxes",
            "cgst_ledger": "Duties & Taxes",
            "sgst_ledger": "Duties & Taxes",
            "tcs_ledger": "Current Assets",
            "tds_ledger": "Current Assets",
            "discount_ledger": "Indirect Expenses",
            "round_off_ledger": "Indirect Expenses",
            "shipping_ledger": "Indirect Incomes",
            "party_ledger": "Sundry Debtors",
        }
        entries.extend(ledger_xml(value, parent_map.get(key, "Sundry Debtors")) for key, value in ledgers.items() if key != "stock_item" and key != "uqc")
        for item in sorted({str(voucher["stock_item"]) for voucher in vouchers}):
            entries.append(stock_item_xml(item, ledgers["uqc"]))
    for voucher in vouchers:
        vch_type = escape(str(voucher["voucher_type"]))
        amount = signed_amount(voucher.get("amount"), str(voucher["voucher_type"]), debit_side=True)
        taxable_amount = signed_amount(voucher.get("taxable_value"), str(voucher["voucher_type"]))
        igst_amount = signed_amount(voucher.get("igst"), str(voucher["voucher_type"]))
        cgst_amount = signed_amount(voucher.get("cgst"), str(voucher["voucher_type"]))
        sgst_amount = signed_amount(voucher.get("sgst"), str(voucher["voucher_type"]))
        voucher_no = escape(str(voucher["voucher_no"]))
        date = str(voucher.get("date") or "").replace("-", "")
        entries.append(f"""
<VOUCHER VCHTYPE="{vch_type}" ACTION="Create">
  <DATE>{escape(date)}</DATE>
  <VOUCHERNUMBER>{voucher_no}</VOUCHERNUMBER>
  <PARTYLEDGERNAME>{escape(voucher["party_ledger"])}</PARTYLEDGERNAME>
  <ALLLEDGERENTRIES.LIST><LEDGERNAME>{escape(voucher["party_ledger"])}</LEDGERNAME><ISDEEMEDPOSITIVE>{"No" if str(voucher["voucher_type"]) == "Credit Note" else "Yes"}</ISDEEMEDPOSITIVE><AMOUNT>{amount}</AMOUNT></ALLLEDGERENTRIES.LIST>
  <ALLLEDGERENTRIES.LIST><LEDGERNAME>{escape(ledgers["sales_ledger"])}</LEDGERNAME><ISDEEMEDPOSITIVE>{"Yes" if str(voucher["voucher_type"]) == "Credit Note" else "No"}</ISDEEMEDPOSITIVE><AMOUNT>{taxable_amount}</AMOUNT></ALLLEDGERENTRIES.LIST>
  <ALLLEDGERENTRIES.LIST><LEDGERNAME>{escape(ledgers["igst_ledger"])}</LEDGERNAME><ISDEEMEDPOSITIVE>{"Yes" if str(voucher["voucher_type"]) == "Credit Note" else "No"}</ISDEEMEDPOSITIVE><AMOUNT>{igst_amount}</AMOUNT></ALLLEDGERENTRIES.LIST>
  <ALLLEDGERENTRIES.LIST><LEDGERNAME>{escape(ledgers["cgst_ledger"])}</LEDGERNAME><ISDEEMEDPOSITIVE>{"Yes" if str(voucher["voucher_type"]) == "Credit Note" else "No"}</ISDEEMEDPOSITIVE><AMOUNT>{cgst_amount}</AMOUNT></ALLLEDGERENTRIES.LIST>
  <ALLLEDGERENTRIES.LIST><LEDGERNAME>{escape(ledgers["sgst_ledger"])}</LEDGERNAME><ISDEEMEDPOSITIVE>{"Yes" if str(voucher["voucher_type"]) == "Credit Note" else "No"}</ISDEEMEDPOSITIVE><AMOUNT>{sgst_amount}</AMOUNT></ALLLEDGERENTRIES.LIST>
  <INVENTORYENTRIES.LIST><STOCKITEMNAME>{escape(str(voucher["stock_item"]))}</STOCKITEMNAME><ACTUALQTY>{money(voucher.get("qty"))} {escape(ledgers["uqc"])}</ACTUALQTY><BILLEDQTY>{money(voucher.get("qty"))} {escape(ledgers["uqc"])}</BILLEDQTY><AMOUNT>{taxable_amount}</AMOUNT></INVENTORYENTRIES.LIST>
</VOUCHER>""")
    return f"""<ENVELOPE><HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER><BODY><IMPORTDATA><REQUESTDESC><REPORTNAME>Vouchers</REPORTNAME><STATICVARIABLES><SVCURRENTCOMPANY>{escape(company_name)}</SVCURRENTCOMPANY></STATICVARIABLES></REQUESTDESC><REQUESTDATA>{''.join(entries)}</REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>"""


def validate_tally_xml(xml: str, vouchers: list[dict]) -> dict:
    return {
        "valid": xml.startswith("<ENVELOPE>") and xml.endswith("</ENVELOPE>") and "<VOUCHER" in xml,
        "voucher_count": len(vouchers),
        "duplicate_vouchers_removed": len(vouchers) != len({(voucher["voucher_no"], voucher["voucher_type"], voucher["source"].get("platform"), voucher["source"].get("gstin"), voucher["source"].get("etin")) for voucher in vouchers}),
    }


def write_voucher_excel(path: Path, vouchers: list[dict]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [{key: safe_excel_value(value) for key, value in voucher.items() if key != "source"} for voucher in vouchers]
    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        pd.DataFrame(rows).to_excel(writer, sheet_name="Voucher Preview", index=False)
        summary = pd.DataFrame([{
            "voucher_count": len(vouchers),
            "taxable_value": sum((money(row.get("taxable_value")) for row in vouchers), Decimal("0.00")),
            "total_tax": sum((money(row.get("total_tax")) for row in vouchers), Decimal("0.00")),
            "amount": sum((money(row.get("amount")) for row in vouchers), Decimal("0.00")),
        }])
        summary.to_excel(writer, sheet_name="Summary", index=False)
    return path
