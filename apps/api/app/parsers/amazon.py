from pathlib import Path

import pandas as pd

from app.parsers.base import MarketplaceParser, ParseResult, clean_column
from app.services.validation import validate_transaction


class AmazonParser(MarketplaceParser):
    platform = "amazon"

    def parse(self, files: list[Path]) -> ParseResult:
        result = ParseResult()
        for path in files:
            try:
                frame = pd.read_csv(path, dtype=object, encoding_errors="ignore")
                frame.columns = [clean_column(col) for col in frame.columns]
                for _, series in frame.iterrows():
                    row = series.to_dict()
                    txn = self.normalize_row(row, path.name)
                    type_blob = " ".join(str(row.get(key, "")) for key in row.keys()).lower()
                    if any(word in type_blob for word in ["refund", "cancel"]):
                        txn["doc_type"] = "credit_note"
                        txn["taxable_value"] = -abs(txn["taxable_value"])
                    errors = validate_transaction(txn)
                    txn["validation_status"] = "error" if errors else "valid"
                    txn["validation_errors"] = "; ".join(errors) if errors else None
                    result.transactions.append(txn)
            except Exception as exc:
                result.errors.append({"file": path.name, "error": str(exc)})
        return result

