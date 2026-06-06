from pathlib import Path
from decimal import Decimal

import pandas as pd
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import dominant_excluded_period
from app.api.routes import run_import_parser
from app.parsers.base import ParseResult
from app.parsers.factory import get_parser
from app.db.session import Base
from app.models.entities import GSTProfile, NormalizedTransaction, PlatformImportBatch, User


def test_custom_schema_platform_parser_preserves_requested_platform_and_etin(tmp_path: Path):
    csv_path = tmp_path / "myntra.csv"
    csv_path.write_text(
        "\n".join(
            [
                "invoice_no,invoice_date,buyer_state_code,hsn,taxable_value,gst_rate,igst",
                "MYN-1,2026-05-12,29,6109,100.00,18,18.00",
            ]
        ),
        encoding="utf-8",
    )

    parser = get_parser("myntra")("29ABCDE1234F1Z5", "052026")
    result = parser.parse([csv_path])

    assert not result.errors
    assert len(result.transactions) == 1
    assert result.transactions[0]["platform"] == "myntra"
    assert result.transactions[0]["etin"] == "29AADCM5146R1C1"


def test_blinkit_generic_parser_preserves_platform_and_supplier_etin(tmp_path: Path):
    csv_path = tmp_path / "blinkit.csv"
    csv_path.write_text(
        "\n".join(
            [
                "invoice_no,invoice_date,buyer_state_code,hsn,taxable_value,gst_rate,igst,ecommerce gstin",
                "BLK-1,2026-05-12,29,2106,250.00,18,45.00,29ABCDE1234F1Z5",
            ]
        ),
        encoding="utf-8",
    )

    parser = get_parser("blinkit")("29ABCDE1234F1Z5", "052026")
    result = parser.parse([csv_path])

    assert not result.errors
    assert len(result.transactions) == 1
    assert result.transactions[0]["platform"] == "blinkit"
    assert result.transactions[0]["etin"] == "29ABCDE1234F1Z5"
    assert result.transactions[0]["validation_status"] == "valid"


def test_dominant_excluded_period_detects_single_period_from_parser_debug():
    result = ParseResult(
        debug={
            "period_excluded_rows": [
                {"document_date": "2026-04-06"},
                {"document_date": "2026-04-14"},
            ]
        }
    )

    assert dominant_excluded_period(result) == "042026"


def test_dominant_excluded_period_ignores_mixed_period_debug():
    result = ParseResult(
        debug={
            "period_excluded_rows": [
                {"document_date": "2026-04-06"},
                {"document_date": "2026-05-14"},
            ]
        }
    )

    assert dominant_excluded_period(result) is None


def test_run_import_parser_auto_switches_flipkart_batch_to_detected_file_period(tmp_path: Path):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        user = User(
            email="seller@example.com",
            password_hash="x",
            role="user",
            plan="admin_free",
            subscription_status="active",
        )
        db.add(user)
        db.flush()
        profile = GSTProfile(
            user_id=user.id,
            gstin="07TCRPS8655B1ZK",
            legal_name="Nayamo",
            trade_name="Nayamo",
            state_code="07",
            filing_frequency="Monthly",
            financial_year="2026-27",
            return_period="052026",
        )
        db.add(profile)
        db.flush()
        batch = PlatformImportBatch(
            user_id=user.id,
            profile_id=profile.id,
            period="052026",
            platform="flipkart",
            status="queued",
        )
        db.add(batch)
        db.commit()

        source = tmp_path / "flipkart.xlsx"
        pd.DataFrame(
            [
                {
                    "Event Type": "Sale",
                    "Invoice No": "LWABOG7270000001",
                    "Invoice Date": "2026-04-05",
                    "Taxable Value": 100,
                    "IGST Rate": 3,
                    "IGST Amount": 3,
                    "Customer's Delivery State": "Maharashtra",
                }
            ]
        ).to_excel(source, sheet_name="Sales Report", index=False)

        run_import_parser(batch, [str(source)], db)
        db.commit()

        row = db.scalar(select(NormalizedTransaction))
        assert batch.period == "042026"
        assert profile.return_period == "042026"
        assert batch.parsed_rows == 1
        assert row is not None
        assert row.platform == "flipkart"
        assert row.filing_period == "042026"
    finally:
        db.close()


def test_run_import_parser_aggregates_meesho_duplicate_financial_lines(tmp_path: Path):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        user = User(
            email="meesho@example.com",
            password_hash="x",
            role="user",
            plan="admin_free",
            subscription_status="active",
        )
        db.add(user)
        db.flush()
        profile = GSTProfile(
            user_id=user.id,
            gstin="07TCRPS8655B1ZK",
            legal_name="Nayamo",
            trade_name="Nayamo",
            state_code="07",
            filing_frequency="Monthly",
            financial_year="2026-27",
            return_period="042026",
        )
        db.add(profile)
        db.flush()
        batch = PlatformImportBatch(
            user_id=user.id,
            profile_id=profile.id,
            period="042026",
            platform="meesho",
            status="queued",
        )
        db.add(batch)
        db.commit()

        source = tmp_path / "tcs_sales.xlsx"
        pd.DataFrame(
            [
                {
                    "sub order num": "278133552897297920_1",
                    "order date": "2026-04-25",
                    "invoice no.": "6p5kc27100",
                    "hsn code": "711790",
                    "quantity": 1,
                    "gst rate": 3,
                    "total taxable sale value": 164.08,
                    "tax amount": 4.92,
                    "total invoice value": 169.00,
                    "end customer state new": "TELANGANA",
                    "eco tcs gstin": "07AARCM9332R1CQ",
                },
                {
                    "sub order num": "278133552897297920_1",
                    "order date": "2026-04-25",
                    "invoice no.": "6p5kc27100",
                    "hsn code": "711790",
                    "quantity": 0,
                    "gst rate": 3,
                    "total taxable sale value": -32.04,
                    "tax amount": -0.96,
                    "total invoice value": -33.00,
                    "end customer state new": "TELANGANA",
                    "eco tcs gstin": "07AARCM9332R1CQ",
                },
            ]
        ).to_excel(source, index=False)

        run_import_parser(batch, [str(source)], db)
        db.commit()

        rows = db.scalars(select(NormalizedTransaction)).all()
        assert batch.parsed_rows == 1
        assert batch.error_rows == 0
        assert len(rows) == 1
        assert rows[0].taxable_value == Decimal("132.04")
        assert rows[0].igst == Decimal("3.96")
        assert rows[0].gross_amount == Decimal("136.00")
        assert rows[0].validation_status == "valid"
    finally:
        db.close()
