# September 2026 GSTR-1 Source-Backed HSN/B2B Audit

## A. Actual B2B Invoices Found

No actual B2B invoices were found in the available September 2026 source data.

- Database check: `normalized_transactions` for GSTIN `07TCRPS8655B1ZK`, period `092026`, with non-empty `recipient_gstin` returned `0` rows.
- Snapdeal Section 5B has `0` rows.
- Snapdeal Section 7(A)(2), Section 7(B)(2), and Section 3 in GSTR-8 are e-commerce/operator aggregate rows, not recipient-GSTIN B2B invoices.
- Flipkart and Meesho September source rows reviewed do not provide registered recipient GSTIN rows for B2B reporting.

## B. Actual B2B HSN Aggregation

No source-backed B2B HSN aggregation exists for September 2026.

Revised `hsn.hsn_b2b`: `[]`

## C. Current hsn_b2b vs Source Comparison

The current portal-compatible JSON had `hsn_b2b` populated with the same rows and totals as `hsn_b2c`:

- `hsn_b2b` txval `38623.22`, IGST `1524.55`, CGST `27.44`, SGST `27.38`
- `hsn_b2c` txval `38623.22`, IGST `1524.55`, CGST `27.44`, SGST `27.38`

This is invalid because no actual B2B source rows were found. The portal B2B HSN validation risk is caused by duplicated B2C rows being present under `hsn_b2b`, not by source-backed B2B supplies.

## D. Blank-HSN Snapdeal Rows and Actual HSN Mapping

Source file: `/home/jarvis/Downloads/Sc8f1c_SEPT_2026_94923732_434144.xlsx`

Snapdeal source rows:

- Section 7(A)(2): aggregate taxable value `171.84`, CGST `2.58`, SGST `2.58`, rate `3%`
- Section 7(B)(2): 8 interstate aggregate rows, total taxable value `2127.14`, IGST `63.86`, rate `3%`
- Section 12: HSN `71171100`, total quantity `13`, total value `2368.00`, total taxable value `2298.98`, IGST `63.86`, CGST `2.58`, SGST `2.58`, cess `0`

Mapping:

| Document/aggregate rows | Source HSN | Rate | Taxable | IGST | CGST | SGST | Cess |
|---|---:|---:|---:|---:|---:|---:|---:|
| SNAPDEAL-7(A)(2)-3 and SNAPDEAL-7(B)(2)-3 through 10 | 71171100 | 3% | 2298.98 | 63.86 | 2.58 | 2.58 | 0 |

## E. Blank-HSN Flipkart Rows and Actual HSN Mapping

Source file: `/home/jarvis/Downloads/900b6926-9f18-4813-bbcc-d9652bc12e7f_1791346852000.xlsx`

The Cash Back Report rows have no HSN column, but each row carries Order ID and Order Item ID. The Sales Report has matching Order ID/Order Item ID with product description and HSN.

| Document | Source Order Item ID | Source Sales HSN | Rate | Taxable | IGST | CGST | SGST | Cess |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| LYAA9U7270000045 | 438509186750864100 | 7117 | 3% | 7.77 | 0.23 | 0 | 0 | 0 |
| LYAA9U7270000046 | 338531354961620100 | 7117 | 3% | 1.55 | 0.05 | 0 | 0 | 0 |
| LYAA9U7270000047 | 438539865909335104 | 7117 | 3% | 7.77 | 0.23 | 0 | 0 | 0 |
| LYAA9U7270000048 | 338544374818284100 | 71131110 | 3% | 7.77 | 0.23 | 0 | 0 | 0 |
| LYAA9U7270000049 | 338599015120465100 | 71131110 | 3% | 6.80 | 0.20 | 0 | 0 | 0 |
| LZAA9B7270000020 | 338456797957045100 | 7117 | 3% | -1.63 | -0.05 | 0 | 0 | 0 |
| LZAA9B7270000021 | 338531354961620100 | 7117 | 3% | -1.55 | -0.05 | 0 | 0 | 0 |

Flipkart cashback HSN aggregate:

| HSN | Rate | Taxable | IGST | CGST | SGST | Cess |
|---:|---:|---:|---:|---:|---:|---:|
| 7117 | 3% | 13.91 | 0.41 | 0 | 0 | 0 |
| 71131110 | 3% | 14.57 | 0.43 | 0 | 0 | 0 |

## F. Revised HSN B2C Totals

Revised source-backed `hsn_b2c` totals:

- txval `40950.68`
- IGST `1589.25`
- CGST `30.02`
- SGST `29.96`
- cess `0`

The taxable value and IGST reconcile to B2CS exactly. CGST/SGST reconcile to SUPECO/source platform totals; B2CS has `29.99`/`29.99`, which appears to be a paise-level split/rounding difference from source-preserved Snapdeal `2.58`/`2.58` and Meesho `27.44`/`27.38`.

## G. Unresolved Rows

No blank-HSN rows remain unresolved from the known September 2026 blank-HSN list.

## H. Remaining Portal-Validation Risks

- `hsn_b2b` must stay empty unless actual recipient-GSTIN B2B rows are found.
- Revised HSN B2C CGST/SGST totals follow source/SUPECO (`30.02`/`29.96`) rather than the B2CS rounded split (`29.99`/`29.99`).
- Existing NIL amount `357.48` remains separate as INTRB2C NIL and is not included in taxable HSN B2C.
- Existing DOC_ISSUE ranges were not changed; invalid Snapdeal serials with parentheses were not reintroduced.
