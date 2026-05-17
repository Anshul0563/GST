from pathlib import Path

from openpyxl import load_workbook
import pandas as pd

from app.parsers.base import MarketplaceParser, ParseResult, clean_column, detect_header_row_frame, unique_headers
from app.services.transaction_normalizer import finalize_transaction


class FlipkartParser(MarketplaceParser):
    platform = "flipkart"

    def parse(self, files: list[Path]) -> ParseResult:
        result = ParseResult()
        for path in files:
            try:
                workbook = load_workbook(path, data_only=True, read_only=False)
                for sheet in workbook.worksheets:
                    rows = list(sheet.iter_rows(values_only=True))
                    if not rows:
                        continue
                    frame = pd.DataFrame(rows)
                    header_index = detect_header_row_frame(frame, ["order", "invoice", "taxable", "igst", "cgst", "sgst"])
                    headers = unique_headers([clean_column(value) or f"column {idx}" for idx, value in enumerate(frame.iloc[header_index].tolist())])
                    data = frame.iloc[header_index + 1:].copy()
                    data.columns = headers
                    data = data.dropna(how="all")
                    if data.empty:
                        continue
                    for _, series in data.iterrows():
                        txn = self.normalize_row(series.to_dict(), f"{path.name}:{sheet.title}")
                        blob = " ".join(str(value) for value in series.to_dict().values()).lower()
                        if "credit note" in blob or "return" in blob:
                            txn["doc_type"] = "credit_note"
                        elif "debit note" in blob:
                            txn["doc_type"] = "debit_note"
                        result.transactions.append(finalize_transaction(txn))
            except Exception as exc:
                result.errors.append({"file": path.name, "error": str(exc)})
        return result
