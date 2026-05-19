from pathlib import Path

import pandas as pd

from app.parsers.base import MarketplaceParser, ParseResult, clean_column, dataframe_from_excel, should_skip_transaction
from app.services.pos_resolver import new_pos_debug, observe_pos_debug, resolve_pos
from app.services.transaction_normalizer import finalize_transaction


class CustomExcelParser(MarketplaceParser):
    platform = "custom"

    def parse(self, files: list[Path]) -> ParseResult:
        result = ParseResult()
        result.debug = new_pos_debug(self.platform)
        for path in files:
            try:
                if path.suffix.lower() == ".csv":
                    frame = pd.read_csv(path, dtype=object, encoding_errors="ignore")
                    frame.columns = [clean_column(col) for col in frame.columns]
                else:
                    frame = dataframe_from_excel(path)
                for index, series in frame.iterrows():
                    txn = self.normalize_row(series.to_dict(), path.name)
                    observe_pos_debug(result.debug, int(index) + 2, resolve_pos(series.to_dict(), txn, self.platform), series.to_dict())
                    if should_skip_transaction(txn):
                        continue
                    result.transactions.append(finalize_transaction(txn))
            except Exception as exc:
                result.errors.append({"file": path.name, "error": str(exc)})
        return result
