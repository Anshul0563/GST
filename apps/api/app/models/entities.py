from datetime import datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    full_name: Mapped[str | None] = mapped_column(String(160))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    profiles: Mapped[list["GSTProfile"]] = relationship(back_populates="user")


class GSTProfile(Base):
    __tablename__ = "gst_profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    gstin: Mapped[str] = mapped_column(String(15), index=True)
    legal_name: Mapped[str] = mapped_column(String(255))
    trade_name: Mapped[str | None] = mapped_column(String(255))
    state_code: Mapped[str] = mapped_column(String(2))
    filing_frequency: Mapped[str] = mapped_column(String(20), default="Monthly")
    financial_year: Mapped[str] = mapped_column(String(9))
    return_period: Mapped[str] = mapped_column(String(6))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    user: Mapped[User] = relationship(back_populates="profiles")


class FilingPeriod(Base):
    __tablename__ = "filing_periods"

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("gst_profiles.id"), index=True)
    period: Mapped[str] = mapped_column(String(6))
    status: Mapped[str] = mapped_column(String(32), default="draft")


class PlatformImportBatch(Base):
    __tablename__ = "platform_import_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("gst_profiles.id"), index=True)
    platform: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(32), default="queued")
    parsed_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_report_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("platform_import_batches.id"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(500))
    content_type: Mapped[str | None] = mapped_column(String(120))
    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class NormalizedTransaction(Base):
    __tablename__ = "normalized_transactions"
    __table_args__ = (UniqueConstraint("profile_id", "platform", "invoice_no", "order_item_id", name="uq_txn_doc_item"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("gst_profiles.id"), index=True)
    batch_id: Mapped[int | None] = mapped_column(ForeignKey("platform_import_batches.id"), index=True)
    platform: Mapped[str] = mapped_column(String(40), index=True)
    gstin: Mapped[str] = mapped_column(String(15), index=True)
    etin: Mapped[str | None] = mapped_column(String(15), index=True)
    filing_period: Mapped[str] = mapped_column(String(6), index=True)
    order_id: Mapped[str | None] = mapped_column(String(120))
    order_item_id: Mapped[str | None] = mapped_column(String(120))
    invoice_no: Mapped[str | None] = mapped_column(String(120), index=True)
    invoice_date: Mapped[datetime | None] = mapped_column(Date)
    doc_type: Mapped[str] = mapped_column(String(20), default="invoice")
    buyer_state_code: Mapped[str | None] = mapped_column(String(2), index=True)
    buyer_state_name: Mapped[str | None] = mapped_column(String(80))
    hsn: Mapped[str | None] = mapped_column(String(20))
    product_name: Mapped[str | None] = mapped_column(String(255))
    sku: Mapped[str | None] = mapped_column(String(120))
    qty: Mapped[Decimal] = mapped_column(Numeric(14, 3), default=0)
    taxable_value: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    gst_rate: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=0)
    igst: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    cgst: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    sgst: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    cess: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    tcs: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    tds: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    gross_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    discount_seller: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    discount_platform: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    settlement_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    source_file: Mapped[str | None] = mapped_column(String(255))
    raw_row_json: Mapped[str | None] = mapped_column(Text)
    validation_status: Mapped[str] = mapped_column(String(20), default="valid")
    validation_errors: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class GSTR1JsonExport(Base):
    __tablename__ = "gstr1_json_exports"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("gst_profiles.id"), index=True)
    period: Mapped[str] = mapped_column(String(6), index=True)
    json_path: Mapped[str | None] = mapped_column(String(500))
    excel_path: Mapped[str | None] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(32), default="generated")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TallyCompany(Base):
    __tablename__ = "tally_companies"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("gst_profiles.id"), index=True)
    company_name: Mapped[str] = mapped_column(String(255))
    tally_guid: Mapped[str | None] = mapped_column(String(120))


class TallyLedgerMapping(Base):
    __tablename__ = "tally_ledger_mappings"

    id: Mapped[int] = mapped_column(primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("tally_companies.id"), index=True)
    mapping_json: Mapped[str] = mapped_column(Text)


class ReconciliationBatch(Base):
    __tablename__ = "reconciliation_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("gst_profiles.id"), index=True)
    status: Mapped[str] = mapped_column(String(32), default="completed")
    report_path: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ReconciliationRow(Base):
    __tablename__ = "reconciliation_rows"

    id: Mapped[int] = mapped_column(primary_key=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("reconciliation_batches.id"), index=True)
    supplier_gstin: Mapped[str | None] = mapped_column(String(15))
    invoice_no: Mapped[str | None] = mapped_column(String(120))
    invoice_date: Mapped[datetime | None] = mapped_column(Date)
    category: Mapped[str] = mapped_column(String(40), index=True)
    books_json: Mapped[str | None] = mapped_column(Text)
    portal_json: Mapped[str | None] = mapped_column(Text)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), index=True)
    action: Mapped[str] = mapped_column(String(80), index=True)
    entity_type: Mapped[str | None] = mapped_column(String(80))
    entity_id: Mapped[str | None] = mapped_column(String(80))
    metadata_json: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

