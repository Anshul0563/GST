from decimal import Decimal
from app.services.validation import money
from app.services.gst import validate_gstr1_schema, validate_doc_issue_ranges

def validate_gstr1_export(payload):
    errors = []
    warnings = []

    errors.extend(validate_gstr1_schema(payload))
    errors.extend(validate_doc_issue_ranges(payload.get("doc_issue", {})))

    b2cs = payload.get("b2cs", [])
    supeco = payload.get("supeco", {}).get("clttx", [])

    for row in b2cs:
        if money(row.get("txval")) < Decimal("0.00"):
            errors.append(f"Negative B2CS taxable for POS {row.get('pos')}")
        if row.get("sply_ty") == "INTER" and money(row.get("iamt")) == Decimal("0.00"):
            warnings.append(f"INTER row has zero IGST for POS {row.get('pos')}")
        if row.get("sply_ty") == "INTRA":
            if abs(money(row.get("camt")) - money(row.get("samt"))) > Decimal("0.01"):
                errors.append(f"CGST/SGST mismatch for POS {row.get('pos')}")

    b2cs_txval = sum(money(x.get("txval")) for x in b2cs)
    eco_txval = sum(money(x.get("suppval")) for x in supeco)

    if abs(b2cs_txval - eco_txval) > Decimal("0.01"):
        errors.append("B2CS taxable total does not match SUPECO taxable total")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
    }