import json
from pathlib import Path

import pandas as pd


EXCEL_FORMULA_PREFIXES = ("=", "+", "-", "@")


def safe_excel_value(value):
    if isinstance(value, str) and value.startswith(EXCEL_FORMULA_PREFIXES):
        return "'" + value
    return value


def write_gstr1_excel(path: Path, payload: dict, rows: list[dict], errors: list[dict] | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    b2cs = pd.DataFrame(payload.get("b2cs", []))
    supeco = pd.DataFrame(payload.get("supeco", {}).get("clttx", payload.get("supeco", {}).get("supeco_det", [])))
    doc_rows = []
    for group in payload.get("doc_issue", {}).get("doc_det", []):
        for doc in group.get("docs", []):
            doc_rows.append({"doc_num": group["doc_num"], **doc})
    raw = pd.DataFrame([{key: safe_excel_value(value) for key, value in row.items() if key != "raw_row_json"} for row in rows])
    platform_summary = raw.groupby("platform", dropna=False)[["taxable_value", "igst", "cgst", "sgst"]].sum().reset_index() if not raw.empty else pd.DataFrame()
    state_summary = raw.groupby("buyer_state_code", dropna=False)[["taxable_value", "igst", "cgst", "sgst"]].sum().reset_index() if not raw.empty else pd.DataFrame()

    with pd.ExcelWriter(path, engine="xlsxwriter") as writer:
        pd.DataFrame([{"gstin": payload["gstin"], "period": payload["fp"], "sections": json.dumps({"b2cs": len(b2cs), "supeco": len(supeco)})}]).to_excel(writer, sheet_name="Summary", index=False)
        b2cs.to_excel(writer, sheet_name="B2CS", index=False)
        supeco.to_excel(writer, sheet_name="SUPECO", index=False)
        pd.DataFrame(doc_rows).to_excel(writer, sheet_name="Document Issue", index=False)
        raw.to_excel(writer, sheet_name="Raw Merged Data", index=False)
        pd.DataFrame(errors or []).to_excel(writer, sheet_name="Error Report", index=False)
        platform_summary.to_excel(writer, sheet_name="Platform Summary", index=False)
        state_summary.to_excel(writer, sheet_name="State Summary", index=False)
    return path
