from pathlib import Path

import pandas as pd

from app.parsers.base import (
    MarketplaceParser,
    ParseResult,
    belongs_to_period,
    clean_column,
    has_explicit_tax_split,
    should_skip_transaction,
)
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

                    if has_explicit_tax_split(row):
                        txn["_preserve_source_tax_split"] = True

                    type_blob = " ".join(
                        str(row.get(key, "")) for key in row.keys()
                    ).lower()

                    if "refund" in type_blob:
                        txn["doc_type"] = "credit_note"
                        credit_note_no = row.get("credit note no") or row.get(
                            "credit note number"
                        )
                        if (
                            credit_note_no not in (None, "")
                            and str(credit_note_no).lower() != "nan"
                        ):
                            txn["invoice_no"] = str(credit_note_no).strip()

                    elif "cancel" in type_blob:
                        txn["doc_type"] = "credit_note"

                    observe_pos_debug(
                        result.debug,
                        int(index) + 2,
                        resolve_pos(row, txn, self.platform),
                        row,
                    )

                    if should_skip_transaction(txn):
                        continue

                    finalized = finalize_transaction(txn)

                    if not belongs_to_period(
                        finalized.get("document_date"),
                        finalized.get("filing_period"),
                    ):
                        result.debug.setdefault("period_excluded_rows", []).append(
                            {
                                "file": path.name,
                                "row": int(index) + 2,
                                "invoice_no": finalized.get("invoice_no"),
                                "doc_type": finalized.get("doc_type"),
                                "document_date": str(finalized.get("document_date")),
                                "taxable_value": str(finalized.get("taxable_value")),
                                "reason": "document date outside filing period",
                            }
                        )
                        continue

                    result.transactions.append(finalized)

            except Exception as exc:
                result.errors.append({"file": path.name, "error": str(exc)})

        return result