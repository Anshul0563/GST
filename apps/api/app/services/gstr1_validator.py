from decimal import Decimal

from app.services.gst import (
    CLEAN_PORTAL,
    GSTTOOL_COMPATIBLE,
    normalize_export_mode,
    validate_doc_issue_ranges,
    validate_gstr1_schema,
)
from app.services.validation import money


def validate_gstr1_export(payload, export_mode=GSTTOOL_COMPATIBLE):
    mode = normalize_export_mode(export_mode)

    errors = []
    warnings = []

    errors.extend(validate_gstr1_schema(payload, mode))
    errors.extend(validate_doc_issue_ranges(payload.get("doc_issue", {})))

    b2cs = payload.get("b2cs", [])
    supeco = payload.get("supeco", {}).get("clttx", [])

    for row in b2cs:
        txval = money(row.get("txval"))
        iamt = money(row.get("iamt"))
        camt = money(row.get("camt"))
        samt = money(row.get("samt"))
        csamt = money(row.get("csamt"))

        if mode == CLEAN_PORTAL and txval < Decimal("0.00"):
            errors.append(f"Negative B2CS taxable for POS {row.get('pos')}")

        if (
            mode == CLEAN_PORTAL
            and row.get("sply_ty") == "INTER"
            and iamt == Decimal("0.00")
            and txval != Decimal("0.00")
        ):
            warnings.append(f"INTER row has zero IGST for POS {row.get('pos')}")

        if row.get("sply_ty") == "INTRA":
            if abs(camt - samt) > Decimal("0.01"):
                errors.append(f"CGST/SGST mismatch for POS {row.get('pos')}")

        if mode == CLEAN_PORTAL and txval == Decimal("0.00"):
            total_tax = iamt + camt + samt + csamt
            if total_tax != Decimal("0.00"):
                errors.append(
                    f"B2CS taxable is zero but GST is non-zero for POS {row.get('pos')}"
                )

    b2cs_txval = sum(money(x.get("txval")) for x in b2cs)
    eco_txval = sum(money(x.get("suppval")) for x in supeco)

    if mode == CLEAN_PORTAL and abs(b2cs_txval - eco_txval) > Decimal("0.01"):
        errors.append("B2CS taxable total does not match SUPECO taxable total")

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
    }