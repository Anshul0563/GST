from pathlib import Path

from app.parsers.base import MarketplaceParser, ParseResult, dataframe_from_excel
from app.services.validation import validate_transaction


class MeeshoParser(MarketplaceParser):
    platform = "meesho"

    def parse(self, files: list[Path]) -> ParseResult:
        result = ParseResult()
        for path in files:
            try:
                frames = []
                xls = dataframe_from_excel(path)
                frames.append(xls)
                for frame in frames:
                    for _, series in frame.iterrows():
                        txn = self.normalize_row(series.to_dict(), path.name)
                        if "return" in path.name.lower() and txn["doc_type"] == "invoice":
                            txn["doc_type"] = "credit_note"
                            txn["taxable_value"] = -abs(txn["taxable_value"])
                        errors = validate_transaction(txn)
                        txn["validation_status"] = "error" if errors else "valid"
                        txn["validation_errors"] = "; ".join(errors) if errors else None
                        result.transactions.append(txn)
            except Exception as exc:
                result.errors.append({"file": path.name, "error": str(exc)})
        return result

