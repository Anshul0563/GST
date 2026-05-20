from pathlib import Path

from openpyxl import load_workbook
import pandas as pd

from app.parsers.base import MarketplaceParser, ParseResult, clean_column, detect_header_row_frame, has_explicit_tax_split, should_skip_transaction, unique_headers
from app.services.pos_resolver import new_pos_debug, observe_pos_debug, resolve_pos
from app.services.transaction_normalizer import finalize_transaction


class FlipkartParser(MarketplaceParser):
    platform = "flipkart"

    def parse(self, files: list[Path]) -> ParseResult:
        result = ParseResult()
        result.debug = new_pos_debug(self.platform)
        for path in files:
            try:
                workbook = load_workbook(path, data_only=True, read_only=False)
                for sheet in workbook.worksheets:
                    rows = list(sheet.iter_rows(values_only=True))
                    if not rows:
                        continue
                    frame = pd.DataFrame(rows)
                    header_index = detect_header_row_frame(frame, ["order", "invoice", "taxable", "igst", "cgst", "sgst"])
                    result.debug["header_rows"].append({"file": path.name, "sheet": sheet.title, "header_row": int(header_index) + 1})
                    headers = unique_headers([clean_column(value) or f"column {idx}" for idx, value in enumerate(frame.iloc[header_index].tolist())])
                    data = frame.iloc[header_index + 1:].copy()
                    data.columns = headers
                    data = data.dropna(how="all")
                    if data.empty:
                        continue
                    for index, series in data.iterrows():
                        row = series.to_dict()
                        txn = self.normalize_row(row, f"{path.name}:{sheet.title}")
                        if has_explicit_tax_split(row):
                            txn["_preserve_source_tax_split"] = True
                        blob = " ".join(str(value) for value in row.values()).lower()
                        document_no = str(txn.get("invoice_no") or "").upper()
                        if document_no.startswith("LZAA") or "debit note" in blob:
                            txn["doc_type"] = "debit_note"
                        elif document_no.startswith(("LYAA", "CAN")) or "credit note" in blob or "return" in blob:
                            txn["doc_type"] = "credit_note"
                        if "cash back report" in sheet.title.lower():
                            txn["_preserve_source_sign"] = True
                            if document_no.startswith("DAL"):
                                txn["doc_type"] = "debit_note"
                        observe_pos_debug(result.debug, int(index) + 1, resolve_pos(row, txn, self.platform), row)
                        if should_skip_transaction(txn):
                            continue
                        result.transactions.append(finalize_transaction(txn))
            except Exception as exc:
                result.errors.append({"file": path.name, "error": str(exc)})
        return result
