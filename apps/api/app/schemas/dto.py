from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str | None = None


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    full_name: str | None = None
    role: str = "user"
    plan: str = "free"
    subscription_status: str = "inactive"
    free_access_reason: str | None = None


class DashboardSummary(BaseModel):
    total_sales: Decimal
    total_taxable_value: Decimal
    total_gst: Decimal
    igst: Decimal
    cgst: Decimal
    sgst: Decimal
    platform_wise_sale: list[dict[str, Any]]
    state_wise_sale: list[dict[str, Any]]
    uploaded_files: int
    pending_errors: int
    json_generation_status: str
    auditor_health_score: int | None = None
    auditor_risk_score: int | None = None
    readiness_status: str | None = None
    auditor_warnings: list[str] | None = None
    auditor_issue_counts: dict[str, int] | None = None


class AuditIssue(BaseModel):
    transaction_id: int | None = None
    platform: str | None = None
    invoice_no: str | None = None
    invoice_date: date | None = None
    issue_type: str
    description: str
    field: str | None = None
    severity: str


class AuditSummary(BaseModel):
    profile_id: int | None = None
    period: str | None = None
    auditor_health_score: int
    auditor_risk_score: int
    readiness_status: str
    issue_counts: dict[str, int]
    warnings: list[str]
    details: list[AuditIssue]


class IssueLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    transaction_id: int | None = None
    profile_id: int
    issue_type: str
    field: str | None = None
    before_value: str | None = None
    after_value: str | None = None
    reason: str
    created_at: datetime


class MarketplaceDetectIn(BaseModel):
    file_contents: str


class AuditFixResponse(BaseModel):
    fixed_count: int
    logs: list[IssueLogOut]
    remaining_issues: int


class MarketplaceDetectResponse(BaseModel):
    marketplace: str
    confidence: int
    reason: str


class GSTProfileIn(BaseModel):
    gstin: str = Field(min_length=15, max_length=15)
    legal_name: str
    trade_name: str | None = None
    filing_frequency: str = "Monthly"
    financial_year: str
    return_period: str


class GSTProfileOut(GSTProfileIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    state_code: str


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    platform: str
    gstin: str
    etin: str | None
    filing_period: str
    order_id: str | None
    order_item_id: str | None
    invoice_no: str | None
    invoice_date: date | None
    document_date: date | None = None
    doc_type: str
    buyer_state_code: str | None
    buyer_state_name: str | None
    hsn: str | None
    product_name: str | None
    sku: str | None
    qty: Decimal
    taxable_value: Decimal
    gst_rate: Decimal
    igst: Decimal
    cgst: Decimal
    sgst: Decimal
    cess: Decimal
    tcs: Decimal
    tds: Decimal
    gross_amount: Decimal
    discount_seller: Decimal
    discount_platform: Decimal
    settlement_amount: Decimal
    source_file: str | None
    validation_status: str
    validation_errors: str | None


class TransactionUpdate(BaseModel):
    buyer_state_code: str | None = None
    buyer_state_name: str | None = None
    hsn: str | None = None
    taxable_value: Decimal | None = None
    gst_rate: Decimal | None = None
    igst: Decimal | None = None
    cgst: Decimal | None = None
    sgst: Decimal | None = None
    cess: Decimal | None = None
    doc_type: str | None = None


class BatchStatus(BaseModel):
    id: int
    platform: str
    period: str | None = None
    status: str
    parsed_rows: int
    error_rows: int
    errors: list[dict[str, Any]] = []
    debug: dict[str, Any] = {}


class GenerateGSTR1In(BaseModel):
    profile_id: int
    period: str
    export_mode: str = "gsttool_compatible"


class TallyCompanyIn(BaseModel):
    profile_id: int
    company_name: str
    gstin: str | None = None
    financial_year: str | None = None
    state: str | None = None
    auto_create_ledger: bool = True
    tally_guid: str | None = None


class TallyGenerateIn(BaseModel):
    profile_id: int
    period: str
    company_id: int
    ledger_mapping: dict[str, str]
    auto_create_ledgers: bool = True


class ReconcileSettingsIn(BaseModel):
    tax_tolerance: Decimal = Decimal("1.00")
    date_tolerance_days: int = 3
    enable_date_tolerance: bool = True
    enable_fuzzy_invoice: bool = True


class CreatePaymentOrderIn(BaseModel):
    plan_id: str
    billing_cycle: str = "monthly"


class VerifyPaymentIn(BaseModel):
    order_id: int
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
