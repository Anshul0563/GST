from pathlib import Path

from app.parsers.base import (
    MarketplaceParser,
    ParseResult,
    dataframe_from_path,
    finalize_period_transaction,
    has_explicit_tax_split,
    should_skip_transaction,
)
from app.services.pos_resolver import new_pos_debug, observe_pos_debug, resolve_pos


class AmazonParser(MarketplaceParser):
    platform = "amazon"

    def parse(self, files: list[Path]) -> ParseResult:
        result = ParseResult()
        result.debug = new_pos_debug(self.platform)

        for path in files:
            try:
                frame = dataframe_from_path(path)

                for index, series in frame.iterrows():
                    row = series.to_dict()
                    type_blob = " ".join(
                        str(row.get(key, "")) for key in row.keys()
                    ).lower()
                    doc_type = None

                    if "refund" in type_blob:
                        doc_type = "credit_note"
                        credit_note_no = row.get("credit note no") or row.get(
                            "credit note number"
                        )
                        if (
                            credit_note_no not in (None, "")
                            and str(credit_note_no).lower() != "nan"
                        ):
                            row["invoice_no"] = str(credit_note_no).strip()

                    elif "cancel" in type_blob:
                        doc_type = "credit_note"

                    if doc_type:
                        row["doc_type"] = doc_type

                    txn = self.normalize_row(row, path.name)

                    if has_explicit_tax_split(row):
                        txn["_preserve_source_tax_split"] = True

                    observe_pos_debug(
                        result.debug,
                        int(index) + 2,
                        resolve_pos(row, txn, self.platform),
                        row,
                    )

                    if should_skip_transaction(txn):
                        continue

                    finalized = finalize_period_transaction(
                        result,
                        txn,
                        source_file=path.name,
                        row_number=int(index) + 2,
                    )
                    if finalized is None:
                        continue

                    result.transactions.append(finalized)

            except Exception as exc:
                result.errors.append({"file": path.name, "error": str(exc)})

        return result
