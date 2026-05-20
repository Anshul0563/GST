from __future__ import annotations

from decimal import Decimal
from typing import Any


def _decimal(value: Any) -> Decimal:
    if value in (None, ""):
        return Decimal("0")
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _zero_b2cs_keys(payload: dict[str, Any]) -> list[tuple[Any, Any, Any, Any]]:
    keys = []
    for row in payload.get("b2cs", []):
        total = sum(
            _decimal(row.get(field))
            for field in ("txval", "iamt", "camt", "samt", "csamt")
        )
        if total == Decimal("0.00"):
            keys.append((row.get("sply_ty"), row.get("rt"), row.get("typ"), row.get("pos")))
    return keys


def _doc_ranges(payload: dict[str, Any]) -> list[tuple[Any, Any, Any, Any, Any]]:
    ranges = []
    for section in payload.get("doc_issue", {}).get("doc_det", []):
        for doc in section.get("docs", []):
            ranges.append(
                (
                    section.get("doc_num"),
                    doc.get("from"),
                    doc.get("to"),
                    doc.get("totnum"),
                    doc.get("cancel"),
                )
            )
    return ranges


def _b2cs_amounts(payload: dict[str, Any]) -> list[tuple[Any, Any, Any, Any, str, str, str, str]]:
    amounts = []
    for row in payload.get("b2cs", []):
        amounts.append(
            (
                row.get("sply_ty"),
                row.get("rt"),
                row.get("typ"),
                row.get("pos"),
                str(_decimal(row.get("txval"))),
                str(_decimal(row.get("iamt"))),
                str(_decimal(row.get("camt"))),
                str(_decimal(row.get("samt"))),
            )
        )
    return amounts


def _section_counts(payload: dict[str, Any]) -> dict[str, int]:
    return {
        "b2cs": len(payload.get("b2cs", [])),
        "supeco.clttx": len(payload.get("supeco", {}).get("clttx", [])),
        "doc_issue.doc_det": len(payload.get("doc_issue", {}).get("doc_det", [])),
        "doc_issue.docs": len(_doc_ranges(payload)),
    }


def _recursive_differences(reference: Any, generated: Any, path: str = "$") -> list[dict[str, Any]]:
    if isinstance(reference, (int, float)) and isinstance(generated, (int, float)):
        if _decimal(reference) != _decimal(generated):
            return [
                {
                    "path": path,
                    "type": "rounding",
                    "reference": reference,
                    "generated": generated,
                }
            ]
        return []
    if type(reference) is not type(generated):
        return [
            {
                "path": path,
                "type": "type_mismatch",
                "reference": type(reference).__name__,
                "generated": type(generated).__name__,
            }
        ]
    if isinstance(reference, dict):
        differences: list[dict[str, Any]] = []
        if list(reference.keys()) != list(generated.keys()):
            differences.append(
                {
                    "path": path,
                    "type": "key_order",
                    "reference": list(reference.keys()),
                    "generated": list(generated.keys()),
                }
            )
        for key in reference.keys() & generated.keys():
            differences.extend(_recursive_differences(reference[key], generated[key], f"{path}.{key}"))
        for key in reference.keys() - generated.keys():
            differences.append({"path": f"{path}.{key}", "type": "missing_key"})
        for key in generated.keys() - reference.keys():
            differences.append({"path": f"{path}.{key}", "type": "extra_key"})
        return differences
    if isinstance(reference, list):
        differences = []
        if len(reference) != len(generated):
            differences.append(
                {
                    "path": path,
                    "type": "list_length",
                    "reference": len(reference),
                    "generated": len(generated),
                }
            )
        for index, (left, right) in enumerate(zip(reference, generated)):
            differences.extend(_recursive_differences(left, right, f"{path}[{index}]"))
        return differences
    if reference != generated:
        return [
            {
                "path": path,
                "type": "value",
                "reference": reference,
                "generated": generated,
            }
        ]
    return []


def compare_against_reference(reference_json: dict[str, Any], generated_json: dict[str, Any]) -> dict[str, Any]:
    differences = _recursive_differences(reference_json, generated_json)

    checks = [
        ("zero_row_parity", _zero_b2cs_keys(reference_json), _zero_b2cs_keys(generated_json)),
        ("document_range_parity", _doc_ranges(reference_json), _doc_ranges(generated_json)),
        (
            "supeco_ordering",
            [row.get("etin") for row in reference_json.get("supeco", {}).get("clttx", [])],
            [row.get("etin") for row in generated_json.get("supeco", {}).get("clttx", [])],
        ),
        ("rounding_parity", _b2cs_amounts(reference_json), _b2cs_amounts(generated_json)),
        ("section_count_parity", _section_counts(reference_json), _section_counts(generated_json)),
    ]
    for check_type, expected, actual in checks:
        if expected != actual:
            differences.append(
                {
                    "path": check_type,
                    "type": check_type,
                    "reference": expected,
                    "generated": actual,
                }
            )

    exact_match = not differences
    total_nodes = max(1, len(str(reference_json)) // 8)
    match_score = 100.0 if exact_match else max(0.0, 100.0 - (len(differences) / total_nodes * 100.0))
    return {
        "match_score": round(match_score, 2),
        "exact_match": exact_match,
        "differences": differences,
    }
