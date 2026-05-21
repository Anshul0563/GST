from pathlib import Path
from datetime import date

from openpyxl import load_workbook
import pandas as pd

from app.parsers.base import (
    MarketplaceParser,
    ParseResult,
    belongs_to_period,
    clean_column,
    detect_header_row_frame,
    has_explicit_tax_split,
    should_skip_transaction,
    unique_headers,
)
from app.services.pos_resolver import (
    new_pos_debug,
    observe_pos_debug,
    resolve_pos,
)
from app.services.transaction_normalizer import finalize_transaction


class FlipkartParser(MarketplaceParser):
    platform = "flipkart"

    def _period_bounds(self) -> tuple[date, date, date]:
        month = int(self.filing_period[:2])
        year = int(self.filing_period[2:])
        start = date(year, month, 1)
        next_month = date(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
        following_month = date(
            next_month.year + (1 if next_month.month == 12 else 0),
            1 if next_month.month == 12 else next_month.month + 1,
            1,
        )
        return start, next_month, following_month

    def _flipkart_series(self, txn: dict) -> str:
        doc_no = str(txn.get("invoice_no") or "").upper()
        if doc_no.startswith("FAWRLX"):
            return "legacy_sales"
        if doc_no.startswith("RAT"):
            return "legacy_returns"
        if doc_no.startswith("CAN"):
            return "legacy_cashback_credit"
        if doc_no.startswith("DAL"):
            return "legacy_cashback_debit"
        if doc_no.startswith("LWAB"):
            return "new_sales"
        if doc_no.startswith("MFAB"):
            return "new_returns"
        if doc_no.startswith("LYAA"):
            return "new_cashback_credit"
        if doc_no.startswith("LZAA"):
            return "new_cashback_debit"
        return "other"

    def _gsttool_window_filter(self, candidates: list[dict]) -> tuple[set[int], dict[int, str]]:
        period_start, next_month, following_month = self._period_bounds()
        in_period_ids: set[int] = set()
        next_period_rows: dict[str, list[tuple[int, date]]] = {}
        current_rows: dict[str, list[tuple[int, date]]] = {}
        has_new_series_in_period = False

        for index, item in enumerate(candidates):
            txn = item["txn"]
            document_date = txn.get("document_date")
            if not isinstance(document_date, date):
                continue
            series = self._flipkart_series(txn)
            if period_start <= document_date < next_month:
                in_period_ids.add(index)
                current_rows.setdefault(series, []).append((index, document_date))
                if series.startswith("new_"):
                    has_new_series_in_period = True
            elif next_month <= document_date < following_month:
                next_period_rows.setdefault(series, []).append((index, document_date))

        included = set(in_period_ids)
        reasons = {index: "document date is inside filing period" for index in included}

        for series, values in next_period_rows.items():
            if series not in {"legacy_sales", "legacy_cashback_credit"}:
                continue
            ordered = sorted(values, key=lambda item: item[1])
            if not ordered:
                continue
            previous = ordered[0][1]
            for index, document_date in ordered:
                if (document_date - previous).days > 1:
                    break
                included.add(index)
                reasons[index] = "Flipkart GSTTool opening next-month continuation"
                previous = document_date

        if not has_new_series_in_period:
            for series in ("legacy_sales", "legacy_returns", "legacy_cashback_credit"):
                ordered = sorted(current_rows.get(series, []), key=lambda item: item[1])
                cutoff = None
                previous = None
                for _, document_date in ordered:
                    if previous and (document_date - previous).days >= 5:
                        cutoff = document_date
                        break
                    previous = document_date
                if cutoff is None:
                    continue
                for index, document_date in ordered:
                    if document_date < cutoff and index in included:
                        included.remove(index)
                        reasons[index] = "Flipkart GSTTool pre-window legacy row"
                    elif document_date >= cutoff and index in included:
                        reasons[index] = "Flipkart GSTTool legacy window row"

        return included, reasons

    def _debug_row(
        self,
        result: ParseResult,
        *,
        file_name: str,
        sheet_name: str,
        row_number: int,
        txn: dict,
        included: bool,
        reason: str,
    ) -> None:
        result.debug.setdefault("row_level_debug", []).append(
            {
                "file": file_name,
                "sheet_name": sheet_name,
                "source_row_number": row_number,
                "invoice_doc_no": txn.get("invoice_no"),
                "doc_type": txn.get("doc_type"),
                "document_date_used": str(txn.get("document_date")),
                "taxable": str(txn.get("taxable_value")),
                "igst": str(txn.get("igst")),
                "cgst": str(txn.get("cgst")),
                "sgst": str(txn.get("sgst")),
                "included": included,
                "reason": reason,
            }
        )

    def parse(self, files: list[Path]) -> ParseResult:
        result = ParseResult()
        result.debug = new_pos_debug(self.platform)
        candidates: list[dict] = []

        for path in files:
            try:
                workbook = load_workbook(
                    path,
                    data_only=True,
                    read_only=False,
                )

                for sheet in workbook.worksheets:
                    rows = list(sheet.iter_rows(values_only=True))

                    if not rows:
                        continue

                    frame = pd.DataFrame(rows)

                    header_index = detect_header_row_frame(
                        frame,
                        ["order", "invoice", "taxable", "igst", "cgst", "sgst"],
                    )

                    result.debug["header_rows"].append(
                        {
                            "file": path.name,
                            "sheet": sheet.title,
                            "header_row": int(header_index) + 1,
                        }
                    )

                    headers = unique_headers(
                        [
                            clean_column(value) or f"column {idx}"
                            for idx, value in enumerate(
                                frame.iloc[header_index].tolist()
                            )
                        ]
                    )

                    data = frame.iloc[header_index + 1 :].copy()
                    data.columns = headers
                    data = data.dropna(how="all")

                    if data.empty:
                        continue

                    for index, series in data.iterrows():
                        row = series.to_dict()

                        txn = self.normalize_row(
                            row,
                            f"{path.name}:{sheet.title}",
                        )

                        if has_explicit_tax_split(row):
                            txn["_preserve_source_tax_split"] = True

                        blob = " ".join(
                            str(value) for value in row.values()
                        ).lower()

                        document_no = str(
                            txn.get("invoice_no") or ""
                        ).upper()

                        if (
                            document_no.startswith("LZAA")
                            or "debit note" in blob
                        ):
                            txn["doc_type"] = "debit_note"

                        elif (
                            document_no.startswith(("LYAA", "CAN"))
                            or "credit note" in blob
                            or "return" in blob
                        ):
                            txn["doc_type"] = "credit_note"

                        if "cash back report" in sheet.title.lower():
                            txn["_preserve_source_sign"] = True

                            if document_no.startswith("DAL"):
                                txn["doc_type"] = "debit_note"

                        observe_pos_debug(
                            result.debug,
                            int(index) + 1,
                            resolve_pos(row, txn, self.platform),
                            row,
                        )

                        source_row_number = int(index) + 1

                        if should_skip_transaction(txn):
                            self._debug_row(
                                result,
                                file_name=path.name,
                                sheet_name=sheet.title,
                                row_number=source_row_number,
                                txn=txn,
                                included=False,
                                reason="empty transaction row",
                            )
                            continue

                        finalized = finalize_transaction(txn)

                        candidates.append(
                            {
                                "txn": finalized,
                                "file_name": path.name,
                                "sheet_name": sheet.title,
                                "source_row_number": source_row_number,
                            }
                        )

            except Exception as exc:
                result.errors.append(
                    {
                        "file": path.name,
                        "error": str(exc),
                    }
                )

        included, reasons = self._gsttool_window_filter(candidates)
        for index, item in enumerate(candidates):
            txn = item["txn"]
            is_included = index in included
            reason = reasons.get(index, "document date outside Flipkart GSTTool window")
            if is_included:
                result.transactions.append(txn)
            else:
                result.debug.setdefault("period_excluded_rows", []).append(
                    {
                        "file": item["file_name"],
                        "sheet": item["sheet_name"],
                        "row": item["source_row_number"],
                        "invoice_no": txn.get("invoice_no"),
                        "doc_type": txn.get("doc_type"),
                        "document_date": str(txn.get("document_date")),
                        "taxable_value": str(txn.get("taxable_value")),
                        "reason": reason,
                    }
                )
            self._debug_row(
                result,
                file_name=item["file_name"],
                sheet_name=item["sheet_name"],
                row_number=item["source_row_number"],
                txn=txn,
                included=is_included,
                reason=reason,
            )

        return result
