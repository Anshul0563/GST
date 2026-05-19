from pathlib import Path

import pandas as pd

from app.parsers.base import MarketplaceParser, ParseResult, clean_column, should_skip_transaction
from app.services.pos_resolver import new_pos_debug, observe_pos_debug, resolve_pos
from app.services.transaction_normalizer import finalize_transaction


class AmazonParser(MarketplaceParser):
    platform = "amazon"

    def parse(self, files: list[Path]) -> ParseResult:
        result = ParseResult()
        result.debug = new_pos_debug(self.platform)
        for path in files:
            try:
                frame = pd.read_csv(path, dtype=object, encoding_errors="ignore")
                frame.columns = [clean_column(col) for col in frame.columns]
                for index, series in frame.iterrows():
                    row = series.to_dict()
                    txn = self.normalize_row(row, path.name)
                    type_blob = " ".join(str(row.get(key, "")) for key in row.keys()).lower()
                    if any(word in type_blob for word in ["refund", "cancel"]):
                        txn["doc_type"] = "credit_note"
                    observe_pos_debug(result.debug, int(index) + 2, resolve_pos(row, txn, self.platform), row)
                    if should_skip_transaction(txn):
                        continue
                    result.transactions.append(finalize_transaction(txn))
            except Exception as exc:
                result.errors.append({"file": path.name, "error": str(exc)})
        return result
