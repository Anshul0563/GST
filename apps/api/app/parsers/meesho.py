from pathlib import Path

from app.parsers.base import MarketplaceParser, ParseResult, excel_frames, first_value, money, should_skip_transaction, text
from app.services.pos_resolver import new_pos_debug, observe_pos_debug, resolve_pos
from app.services.transaction_normalizer import finalize_transaction


SUBORDER_ALIASES = ["suborder no.", "sub order num", "suborder number", "sub order number", "sub order no", "order id"]


def suborder_key(row: dict) -> str | None:
    return text(first_value(row, SUBORDER_ALIASES))


def has_financial_values(row: dict) -> bool:
    fields = [
        "total taxable sale value",
        "taxable value",
        "taxable amount",
        "tax amount",
        "total invoice value",
        "invoice amount",
        "gross amount",
    ]
    return any(money(first_value(row, fields)) != 0 for _ in [0])


class MeeshoParser(MarketplaceParser):
    platform = "meesho"

    def parse(self, files: list[Path]) -> ParseResult:
        result = ParseResult()
        result.debug = new_pos_debug(self.platform)
        loaded_frames: list[tuple[Path, str, object]] = []
        metadata_by_suborder: dict[str, dict[str, object]] = {}
        for path in files:
            try:
                frames = excel_frames(path)
                for _, frame in frames:
                    for _, series in frame.iterrows():
                        row = series.to_dict()
                        suborder = suborder_key(row)
                        if not suborder:
                            continue
                        metadata = metadata_by_suborder.setdefault(suborder, {})
                        values = {
                            "invoice no": first_value(row, ["invoice no.", "invoice no", "invoice number", "tax invoice no"]),
                            "invoice date": first_value(row, ["invoice date", "order date"]),
                            "hsn": first_value(row, ["hsn", "hsn code", "hsn/sac"]),
                            "product description": first_value(row, ["product description", "product name", "product title", "item description"]),
                            "end customer state new": first_value(row, ["end customer state new", "customer state", "delivery state", "shipping state", "recipient state", "buyer state", "place of supply", "pos", "state"]),
                        }
                        for key, value in values.items():
                            if value not in (None, ""):
                                metadata[key] = value
                for sheet_name, frame in frames:
                    loaded_frames.append((path, sheet_name, frame))
            except Exception as exc:
                result.errors.append({"file": path.name, "error": str(exc)})
        for path, sheet_name, frame in loaded_frames:
            for index, series in frame.iterrows():
                row = series.to_dict()
                if not has_financial_values(row):
                    continue
                suborder = suborder_key(row)
                metadata = metadata_by_suborder.get(suborder or "", {})
                for key, value in metadata.items():
                    row.setdefault(key, value)
                if metadata.get("invoice no") and not first_value(row, ["invoice no.", "invoice no", "invoice number", "tax invoice no"]):
                    row["invoice no"] = metadata["invoice no"]
                if metadata.get("end customer state new") and not first_value(row, ["end customer state new", "customer state", "delivery state", "shipping state", "recipient state", "buyer state", "place of supply", "pos", "state"]):
                    row["resolved state"] = metadata["end customer state new"]
                txn = self.normalize_row(row, f"{path.name}:{sheet_name}")
                is_return = "return" in path.name.lower() or first_value(row, ["cancel return date", "return date"]) not in (None, "")
                if is_return and txn["doc_type"] == "invoice":
                    txn["doc_type"] = "credit_note"
                if not txn.get("invoice_no"):
                    result.errors.append({
                        "file": path.name,
                        "sheet": sheet_name,
                        "row": int(index) + 2,
                        "suborder": suborder,
                        "error": "Missing Meesho invoice metadata for financial row",
                    })
                    continue
                observe_pos_debug(result.debug, int(index) + 2, resolve_pos(row, txn, self.platform), row)
                if should_skip_transaction(txn):
                    continue
                result.transactions.append(finalize_transaction(txn))
        result.debug["meesho_metadata_rows"] = len(metadata_by_suborder)
        result.debug["meesho_financial_rows"] = len(result.transactions)
        return result
