# GSTTool Behavioral Clone Audit

## Scope

This project must clone GSTTool export behavior, not implement theoretical GST cleanup. The audited path is:

Marketplace parser -> transaction normalizer -> GSTR-1 JSON builder -> parity validator -> Excel workbook builder -> frontend export controls.

## Fixed During Audit

- Parser source-tax preservation:
  - Amazon, Flipkart, and Custom Excel now mark rows with explicit IGST/CGST/SGST source columns.
  - `finalize_transaction` preserves explicit source tax split instead of recomputing by POS.
  - Header alias lookup now prioritizes specific amount columns before broad GST labels, fixing Flipkart `SGST Rate` being read instead of `SGST Amount`.
  - Meesho total-tax rows still split because the source often carries only aggregate tax.

- GSTTool-compatible B2CS behavior:
  - Preserves zero B2CS rows in GSTTool mode.
  - Uses GSTTool POS ordering for known original GSTTool output order.
  - Uses GSTTool equal-half split for Meesho total-tax INTRA rows.
  - Reproduces GSTTool's Meesho INTER B2CS gross-backed taxable/tax behavior while leaving SUPECO on source tax values.
  - Reproduces observed GSTTool POS 04 -> POS 03 non-zero B2CS behavior while preserving POS 04 as a zero row.
  - Keeps Clean Portal mode separate for stricter cleanup.

- SUPECO behavior:
  - GSTTool mode orders ETINs by observed GSTTool priority.
  - Meesho total-tax CGST/SGST uses GSTTool equal-half behavior.
  - Explicit source tax split rows are preserved.

- Document issue behavior:
  - GSTTool mode preserves weird cross-prefix ranges.
  - Flipkart sales/cashback/debit streams are grouped separately so credit-note ranges do not collapse into one mega-range.
  - GSTTool mode counts document rows using observed original behavior, including Meesho credit-note row count quirks and Amazon invoice unique-doc counts.
  - Clean Portal mode still splits ranges logically.

- Excel export:
  - Final GSTR-1 workbook no longer uses raw pandas sheet dumps.
  - New openpyxl workbook builder provides merged title rows, styles, borders, widths, freeze panes, filters, print layout, and GST section rendering.

- Frontend:
  - GSTR-1 page has Export Mode toggle.
  - GSTTool Compatible is the default.
  - Match score and compatibility badges are surfaced.

## Verified

- Backend tests: 37 run, 35 pass, 2 skipped because unavailable April/raw GSTTool fixture files.
- Fresh March raw parser rebuild now matches the original GSTTool March JSON exactly:
  - `match_score`: 100.0
  - `exact_match`: true
  - Checks include structure, ordering, B2CS zero rows, rounding, SUPECO, and doc_issue ranges/counts.
- Frontend production build passes.
- Workbook structural check passes for merged title rows, freeze panes, filters, auto widths, and landscape print layout.

## Current DB Parity Finding

Using stale imported local SQLite March rows (`profile_id=4`) against:

`/home/jarvis/Downloads/GSTR1_returns_07TCRPS8655B1ZK_monthly_032026.json`

Earlier stale-row parity score: 82.28%.

Reason: those DB rows were imported before parser-level source tax preservation and grouping fixes. A fresh parse from the March raw marketplace files now reaches exact 100% parity. Stored normalized rows must be re-imported to reflect the fixed behavior in the app database.

## Remaining High-Risk Areas

- Raw marketplace fixtures are not all consistently available in this workspace:
  - Some tests skip because April raw source files are missing from expected paths.
  - March raw files are present and now covered by a true parser-to-GSTTool end-to-end golden test.

- Existing imported DB rows are stale:
  - Parser changes are not retroactive.
  - Stored normalized rows must be deleted/re-imported or migrated if exact local DB parity is required.

## Rule Going Forward

Do not “fix” GSTTool quirks in GSTTool Compatible mode. Any portal-safe cleanup belongs only in Clean Portal mode.
