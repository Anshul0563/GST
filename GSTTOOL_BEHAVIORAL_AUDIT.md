# GSTTool Behavioral Clone Audit

## Scope

This project must clone GSTTool export behavior, not implement theoretical GST cleanup. The audited path is:

Marketplace parser -> transaction normalizer -> GSTR-1 JSON builder -> parity validator -> Excel workbook builder -> frontend export controls.

## Fixed During Audit

- Parser source-tax preservation:
  - Amazon, Flipkart, and Custom Excel now mark rows with explicit IGST/CGST/SGST source columns.
  - `finalize_transaction` preserves explicit source tax split instead of recomputing by POS.
  - Meesho total-tax rows still split because the source often carries only aggregate tax.

- GSTTool-compatible B2CS behavior:
  - Preserves zero B2CS rows in GSTTool mode.
  - Uses GSTTool POS ordering for known original GSTTool output order.
  - Uses GSTTool equal-half split for Meesho total-tax INTRA rows.
  - Keeps Clean Portal mode separate for stricter cleanup.

- SUPECO behavior:
  - GSTTool mode orders ETINs by observed GSTTool priority.
  - Meesho total-tax CGST/SGST uses GSTTool equal-half behavior.
  - Explicit source tax split rows are preserved.

- Document issue behavior:
  - GSTTool mode preserves weird cross-prefix ranges.
  - Flipkart sales/cashback/debit streams are grouped separately so credit-note ranges do not collapse into one mega-range.
  - Clean Portal mode still splits ranges logically.

- Excel export:
  - Final GSTR-1 workbook no longer uses raw pandas sheet dumps.
  - New openpyxl workbook builder provides merged title rows, styles, borders, widths, freeze panes, filters, print layout, and GST section rendering.

- Frontend:
  - GSTR-1 page has Export Mode toggle.
  - GSTTool Compatible is the default.
  - Match score and compatibility badges are surfaced.

## Verified

- Backend tests: 36 run, 34 pass, 2 skipped because unavailable external/raw GSTTool fixture files.
- Frontend production build passes.
- Workbook structural check passes for merged title rows, freeze panes, filters, auto widths, and landscape print layout.

## Current DB Parity Finding

Using the current local SQLite March profile (`profile_id=4`) against:

`/home/jarvis/Downloads/GSTR1_returns_07TCRPS8655B1ZK_monthly_032026.json`

Current parity score: 82.28%.

Reason: those DB rows were imported before parser-level source tax preservation and grouping fixes. The generated output still reflects old normalized row values in the database. Re-importing the same raw marketplace files through the fixed parsers is required for a fair post-fix parity run.

## Remaining High-Risk Areas

- GSTTool document ordering is source/order dependent and inconsistent across March/April references:
  - March JSON order: Meesho, Amazon, Flipkart for invoice docs.
  - April golden JSON order: Meesho, Flipkart, Amazon for invoice docs.
  - This likely depends on original GSTTool upload/session ordering, not pure lexical ordering.

- Raw marketplace fixtures are not all consistently available in this workspace:
  - Some tests skip because April raw source files are missing from expected paths.
  - Golden output tests exist, but true parser-to-GSTTool end-to-end parity needs raw marketplace files present.

- Existing imported DB rows are stale:
  - Parser changes are not retroactive.
  - Stored normalized rows must be deleted/re-imported or migrated if exact local DB parity is required.

## Rule Going Forward

Do not “fix” GSTTool quirks in GSTTool Compatible mode. Any portal-safe cleanup belongs only in Clean Portal mode.
