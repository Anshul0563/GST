from pathlib import Path

import pandas as pd

from app.parsers.base import MarketplaceParser, ParseResult, clean_column, dataframe_from_excel
from app.services.validation import validate_transaction


class CustomExcelParser(MarketplaceParser):
    platform = "custom"

    def parse(self, files: list[Path]) -> ParseResult:
        result = ParseResult()
        for path in files:
            try:
                if path.suffix.lower() == ".csv":
                    frame = pd.read_csv(path, dtype=object, encoding_errors="ignore")
                    frame.columns = [clean_column(col) for col in frame.columns]
                else:
                    frame = dataframe_from_excel(path)
                for _, series in frame.iterrows():
                    txn = self.normalize_row(series.to_dict(), path.name)
                    errors = validate_transaction(txn)
                    txn["validation_status"] = "error" if errors else "valid"
                    txn["validation_errors"] = "; ".join(errors) if errors else None
                    result.transactions.append(txn)
            except Exception as exc:
                result.errors.append({"file": path.name, "error": str(exc)})
        return result

