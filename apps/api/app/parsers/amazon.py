from pathlib import Path

from app.parsers.base import (
    MarketplaceParser,
    ParseResult,
    dataframe_from_path,
    finalize_period_transaction,
    first_value,
    has_explicit_tax_split,
    should_skip_transaction,
    text,
)
from app.services.pos_resolver import new_pos_debug, observe_pos_debug, resolve_pos


AMAZON_TRANSACTION_TYPE_FIELDS = [
    "transaction type",
    "transaction_type",
    "document type",
    "doc_type",
    "type",
    "event type",
    "transaction event type",
]

AMAZON_CREDIT_NOTE_FIELDS = [
    "credit note no",
    "credit note number",
    "credit_note_no",
    "credit_note_number",
]


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
                    transaction_type = (
                        text(first_value(row, AMAZON_TRANSACTION_TYPE_FIELDS)) or ""
                    ).lower()
                    doc_type = None

                    if any(
                        marker in transaction_type
                        for marker in ("refund", "return", "cancel", "credit")
                    ):
                        doc_type = "credit_note"
                        credit_note_no = text(
                            first_value(row, AMAZON_CREDIT_NOTE_FIELDS)
                        )
                        if credit_note_no:
                            row["invoice_no"] = credit_note_no

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
