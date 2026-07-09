# Final Reconciliation Report

## Files Read
- `/home/jarvis/Downloads/gst_3412749_6_2026/tcs_sales.xlsx`
- `/home/jarvis/Downloads/gst_3412749_6_2026/tcs_sales_return.xlsx`
- `/home/jarvis/Downloads/3412749_2026-06-01_2026-06-30_TAX_INVOICE/Tax_invoice_details.xlsx`
- `/home/jarvis/Documents/IT/GST/exports/gst_bharat_gstr1_07TCRPS8655B1ZK_042026.json`

## Period Finding
- Source sales manifest periods: ['2026-06']
- Source return/cancel periods: ['2026-06']
- Website JSON period: `042026`
- Conclusion: the Excel source files are June 2026 (`062026`) while the supplied GSTR JSON is April 2026 (`042026`). This is a hard mismatch in the uploaded data set.

## A. Summary Comparison Table
| Metric | Original Excel | Website GSTR JSON | Difference |
| --- | --- | --- | --- |
| Taxable Value | 19,474.34 | 21,565.88 | 2,091.54 |
| IGST | 535.46 | 628.95 | 93.49 |
| CGST | 24.41 | 9.01 | -15.40 |
| SGST | 24.38 | 9.01 | -15.37 |
| Total GST | 584.25 | 646.97 | 62.72 |
| Invoice Value | 20,058.59 | 22,212.85 | 2,154.26 |

## Count Comparison
| Metric | Original Excel | Website GSTR JSON | Difference |
| --- | --- | --- | --- |
| Invoice Count | 197 | 190 | -7 |
| Credit Note Count | 51 | 46 | -5 |
| B2CS Group Rows | 24 | 24 | 0 |

## Original Excel Calculations
- Gross Taxable Value: 28,091.04
- Gross GST: 842.71
- Gross Invoice Value: 28,933.75
- Total Sales Returns: 8,616.70
- Total Return GST: 258.46
- Return Invoice Value: 8,875.16
- Net Taxable Value: 19,474.34
- Net GST: 584.25
- Net Invoice Value: 20,058.59
- Net IGST: 535.46
- Net CGST: 24.41
- Net SGST: 24.38
- Net CESS: 0.00
- Invoice Count: 197
- Credit Note Count: 51

## Website GSTR JSON Calculations
- Taxable Value: 21,565.88
- IGST: 628.95
- CGST: 9.01
- SGST: 9.01
- CESS: 0.00
- Total GST: 646.97
- Invoice Value: 22,212.85
- B2CS Group Count: 24
- Invoice Count from doc_issue: 190
- Credit Note Count from doc_issue: 46

## Mismatch Findings
- Missing invoices: 190 source invoices are absent from JSON document ranges.
- Extra invoices: 18 JSON invoice documents are absent from source Excel.
- Missing credit notes: 51 source credit notes are absent from JSON credit-note ranges.
- Extra credit notes: 46 JSON credit notes are absent from source return Excel.
- Duplicate invoices in source: 7
- Duplicate returns in source: 0
- Source row GST calculation differences over 0.01: 0
- Taxable group differences over 0.01: 27

## Rounding Review
- Sum of source row GST minus rounded taxable*rate differences: 0.00
- Because the JSON and Excel are different periods, the overall difference is not explained by rounding. Rounding was checked invoice by invoice in the `All Source Rows` sheet and material differences are in `D GST Difference`.

## Website Logic Review
- `build_gstr1_json()` filters rows strictly by `row_belongs_to_period(row, period)` before building B2CS/SUPECO/doc_issue.
- B2CS JSON is aggregated by supply type, GST rate, POS and type. It does not contain invoice-level rows, so invoice-by-invoice comparison is only possible against `doc_issue` ranges and source rows, not against B2CS line items.
- For GSTTool-compatible export, the code has parity quirks: Meesho INTER B2CS can be computed from rounded gross group, zero rows for 3 percent can be retained, POS `04` may remap to `03`, and hard-coded field adjustments exist for some periods. These are in `apps/api/app/services/gst.py`.
- The supplied JSON contains Amazon and Flipkart SUPECO/doc_issue data, but the supplied Excel trio contains only Meesho files. That mismatch cannot come from rounding; it means the JSON was generated from a different upload/batch or period than the provided Excel files.

## Final Answers
- Why is the Original Net Taxable Value different from the GSTR JSON? Because the original Excel files are June 2026 Meesho source files, while the website JSON is April 2026 and includes Meesho, Flipkart and Amazon data. The datasets are not the same filing period/source population.
- Which invoices caused the difference? All June source invoices absent from the April JSON ranges are in `B Missing Invoices`; April JSON extra invoice ranges are in `Extra Invoices`.
- Which credit notes caused the difference? June source credit notes absent from April JSON ranges are in `C Missing Credit Notes`; April JSON extra credit notes are in `Extra Credit Notes`.
- Is the website generating the correct GSTR-1? Not for these Excel files. The supplied JSON cannot be the correct GSTR-1 for the supplied June files.
- What code or logic should be fixed? The generation flow should prevent exporting a period that does not match the uploaded file period, bind exports to a selected import batch, and reject/warn about mixed-platform rows when the selected source files are only Meesho. The relevant logic is the export row selection before `build_gstr1_json()` and the period filter in `apps/api/app/services/gst.py`.

Full workbook: `/home/jarvis/Documents/IT/GST/reconciliation_reports/complete_reconciliation_report.xlsx`