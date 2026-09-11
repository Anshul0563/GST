from decimal import Decimal

from app.services.gst import build_gstr1_json


SELLER = "07ABCDE1234F1Z5"


def transaction(**overrides):
    row = {
        "platform": "amazon",
        "gstin": SELLER,
        "etin": "99ABCDE1234F1Z5",
        "filing_period": "082026",
        "invoice_no": "INV-1",
        "doc_type": "invoice",
        "buyer_state_code": "04",
        "taxable_value": Decimal("100.00"),
        "gst_rate": Decimal("3.00"),
        "igst": Decimal("3.00"),
        "cgst": Decimal("0.00"),
        "sgst": Decimal("0.00"),
        "cess": Decimal("0.00"),
        "qty": Decimal("1.00"),
        "gross_amount": Decimal("103.00"),
        "hsn": "7117",
        "uqc": "PCS",
        "validation_status": "valid",
    }
    row.update(overrides)
    return row


def test_sections_are_derived_from_pos_rate_nil_hsn_and_document_type():
    rows = [
        transaction(invoice_no="INV-1"),
        transaction(
            invoice_no="INV-2",
            taxable_value=Decimal("50.00"),
            gst_rate=Decimal("18.00"),
            igst=Decimal("9.00"),
            gross_amount=Decimal("59.00"),
            hsn="9983",
        ),
        transaction(
            invoice_no="NIL-1",
            buyer_state_code="27",
            taxable_value=Decimal("10.00"),
            gst_rate=Decimal("0.00"),
            igst=Decimal("0.00"),
            gross_amount=Decimal("10.00"),
            hsn="9999",
        ),
        transaction(
            invoice_no="CN-1",
            doc_type="credit_note",
            taxable_value=Decimal("-20.00"),
            igst=Decimal("-0.60"),
            gross_amount=Decimal("-20.60"),
        ),
    ]

    payload = build_gstr1_json(SELLER, "082026", rows)

    b2cs_keys = {
        (row["pos"], Decimal(str(row["rt"]))) for row in payload["b2cs"]
    }
    assert ("04", Decimal("3")) in b2cs_keys
    assert ("04", Decimal("18")) in b2cs_keys
    assert all(row["rt"] != 0 for row in payload["b2cs"])
    assert payload["nil"]["inv"] == [
        {"sply_ty": "INTRB2B", "nil_amt": 0, "expt_amt": 0, "ngsup_amt": 0},
        {"sply_ty": "INTRAB2B", "nil_amt": 0, "expt_amt": 0, "ngsup_amt": 0},
        {"sply_ty": "INTRB2C", "nil_amt": 10, "expt_amt": 0, "ngsup_amt": 0},
        {"sply_ty": "INTRAB2C", "nil_amt": 0, "expt_amt": 0, "ngsup_amt": 0},
    ]
    assert {row["hsn_sc"] for row in payload["hsn"]["hsn_b2c"]} == {"7117", "9983"}
    assert any(
        section["doc_num"] == 5
        for section in payload["doc_issue"]["doc_det"]
    )


def test_period_filter_and_empty_nil_section_are_dynamic():
    row = transaction(filing_period="092026", invoice_no="SEP-1")
    payload = build_gstr1_json(SELLER, "092026", [row])
    assert payload["fp"] == "092026"
    assert "nil" not in payload


def test_supplier_summary_uses_source_signs_without_marketplace_adjustments():
    row = transaction(
        taxable_value=Decimal("-20.00"),
        igst=Decimal("0.00"),
        cgst=Decimal("-0.30"),
        sgst=Decimal("-0.31"),
        gross_amount=Decimal("-20.61"),
        doc_type="credit_note",
    )
    payload = build_gstr1_json(SELLER, "082026", [row])
    summary = payload["supeco"]["clttx"][0]
    assert summary["cgst"] == -0.3
    assert summary["sgst"] == -0.31
