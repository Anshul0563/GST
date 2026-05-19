from pathlib import Path

from app.parsers.base import MarketplaceParser, ParseResult, excel_frames, first_value, should_skip_transaction, text
from app.services.pos_resolver import new_pos_debug, observe_pos_debug, resolve_pos
from app.services.transaction_normalizer import finalize_transaction


class MeeshoParser(MarketplaceParser):
    platform = "meesho"

    def parse(self, files: list[Path]) -> ParseResult:
        result = ParseResult()
        result.debug = new_pos_debug(self.platform)
        loaded_frames: list[tuple[Path, str, object]] = []
        state_by_suborder: dict[str, object] = {}
        for path in files:
            try:
                frames = excel_frames(path)
                for _, frame in frames:
                    for _, series in frame.iterrows():
                        row = series.to_dict()
                        suborder = text(first_value(row, ["suborder no.", "sub order num", "suborder number", "sub order number", "sub order no", "order id"]))
                        state = first_value(row, ["end customer state new", "customer state", "delivery state", "shipping state", "recipient state", "buyer state", "place of supply", "pos", "state"])
                        if suborder and state not in (None, ""):
                            state_by_suborder[suborder] = state
                for sheet_name, frame in frames:
                    loaded_frames.append((path, sheet_name, frame))
            except Exception as exc:
                result.errors.append({"file": path.name, "error": str(exc)})
        for path, sheet_name, frame in loaded_frames:
            for index, series in frame.iterrows():
                row = series.to_dict()
                suborder = text(first_value(row, ["suborder no.", "sub order num", "suborder number", "sub order number", "sub order no", "order id"]))
                if suborder and "resolved state" not in row and suborder in state_by_suborder:
                    row["resolved state"] = state_by_suborder[suborder]
                txn = self.normalize_row(row, f"{path.name}:{sheet_name}")
                if "return" in path.name.lower() and txn["doc_type"] == "invoice":
                    txn["doc_type"] = "credit_note"
                observe_pos_debug(result.debug, int(index) + 2, resolve_pos(row, txn, self.platform), row)
                if should_skip_transaction(txn):
                    continue
                result.transactions.append(finalize_transaction(txn))
        return result
