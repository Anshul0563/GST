from pathlib import Path

from app.parsers.base import MarketplaceParser, ParseResult, excel_frames, should_skip_transaction
from app.services.pos_resolver import new_pos_debug, observe_pos_debug, resolve_pos
from app.services.transaction_normalizer import finalize_transaction


class MeeshoParser(MarketplaceParser):
    platform = "meesho"

    def parse(self, files: list[Path]) -> ParseResult:
        result = ParseResult()
        result.debug = new_pos_debug(self.platform)
        for path in files:
            try:
                for sheet_name, frame in excel_frames(path):
                    for index, series in frame.iterrows():
                        txn = self.normalize_row(series.to_dict(), f"{path.name}:{sheet_name}")
                        if "return" in path.name.lower() and txn["doc_type"] == "invoice":
                            txn["doc_type"] = "credit_note"
                        observe_pos_debug(result.debug, int(index) + 2, resolve_pos(series.to_dict(), txn, self.platform), series.to_dict())
                        if should_skip_transaction(txn):
                            continue
                        result.transactions.append(finalize_transaction(txn))
            except Exception as exc:
                result.errors.append({"file": path.name, "error": str(exc)})
        return result
