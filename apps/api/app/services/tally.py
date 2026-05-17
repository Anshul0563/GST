from decimal import Decimal
from html import escape

from app.services.validation import money


DEFAULT_LEDGERS = {
    "sales": "Online Sales",
    "igst": "Output IGST",
    "cgst": "Output CGST",
    "sgst": "Output SGST",
    "tcs": "TCS Receivable",
    "tds": "TDS Receivable",
    "discount": "Discount Allowed",
    "round_off": "Round Off",
    "party": "eCommerce Debtors",
    "stock_item": "Marketplace Item",
    "uqc": "NOS",
}


def ledger_xml(name: str) -> str:
    escaped = escape(name)
    return f"<LEDGER NAME=\"{escaped}\" RESERVEDNAME=\"\"><NAME>{escaped}</NAME><PARENT>Sundry Debtors</PARENT><ISBILLWISEON>Yes</ISBILLWISEON></LEDGER>"


def build_tally_xml(company_name: str, rows: list[dict], mapping: dict[str, str] | None = None, auto_create_ledgers: bool = True) -> str:
    ledgers = {**DEFAULT_LEDGERS, **(mapping or {})}
    entries: list[str] = []
    if auto_create_ledgers:
        entries.extend(ledger_xml(value) for value in ledgers.values())
    for row in rows:
        amount = money(row.get("gross_amount")) or money(row.get("taxable_value")) + money(row.get("igst")) + money(row.get("cgst")) + money(row.get("sgst"))
        voucher_no = escape(str(row.get("invoice_no") or row.get("order_id") or "NA"))
        date = str(row.get("invoice_date") or "").replace("-", "")
        entries.append(f"""
<VOUCHER VCHTYPE="Sales" ACTION="Create">
  <DATE>{escape(date)}</DATE>
  <VOUCHERNUMBER>{voucher_no}</VOUCHERNUMBER>
  <PARTYLEDGERNAME>{escape(ledgers["party"])}</PARTYLEDGERNAME>
  <ALLLEDGERENTRIES.LIST><LEDGERNAME>{escape(ledgers["party"])}</LEDGERNAME><ISDEEMEDPOSITIVE>Yes</ISDEEMEDPOSITIVE><AMOUNT>-{amount}</AMOUNT></ALLLEDGERENTRIES.LIST>
  <ALLLEDGERENTRIES.LIST><LEDGERNAME>{escape(ledgers["sales"])}</LEDGERNAME><ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE><AMOUNT>{money(row.get("taxable_value"))}</AMOUNT></ALLLEDGERENTRIES.LIST>
  <ALLLEDGERENTRIES.LIST><LEDGERNAME>{escape(ledgers["igst"])}</LEDGERNAME><ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE><AMOUNT>{money(row.get("igst"))}</AMOUNT></ALLLEDGERENTRIES.LIST>
  <ALLLEDGERENTRIES.LIST><LEDGERNAME>{escape(ledgers["cgst"])}</LEDGERNAME><ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE><AMOUNT>{money(row.get("cgst"))}</AMOUNT></ALLLEDGERENTRIES.LIST>
  <ALLLEDGERENTRIES.LIST><LEDGERNAME>{escape(ledgers["sgst"])}</LEDGERNAME><ISDEEMEDPOSITIVE>No</ISDEEMEDPOSITIVE><AMOUNT>{money(row.get("sgst"))}</AMOUNT></ALLLEDGERENTRIES.LIST>
</VOUCHER>""")
    return f"""<ENVELOPE><HEADER><TALLYREQUEST>Import Data</TALLYREQUEST></HEADER><BODY><IMPORTDATA><REQUESTDESC><REPORTNAME>Vouchers</REPORTNAME><STATICVARIABLES><SVCURRENTCOMPANY>{escape(company_name)}</SVCURRENTCOMPANY></STATICVARIABLES></REQUESTDESC><REQUESTDATA>{''.join(entries)}</REQUESTDATA></IMPORTDATA></BODY></ENVELOPE>"""

