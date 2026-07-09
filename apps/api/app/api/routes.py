from datetime import datetime, timedelta
from collections import Counter
from decimal import Decimal
from pathlib import Path
import json
import shutil
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, Header, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.services.gstr1_validator import validate_gstr1_export

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.db.session import get_db
from app.models.entities import (
    AuditLog,
    GSTProfile,
    GSTR1JsonExport,
    NormalizedTransaction,
    PaymentOrder,
    PlatformImportBatch,
    ReconciliationBatch,
    ReconciliationReport,
    ReconciliationRow,
    TallyCompany,
    TallyExport,
    TallyLedgerMapping,
    TallyVoucher,
    UploadedFile,
    User,
    IssueLog,
)
from app.parsers.factory import PARSERS, get_parser
from app.schemas.dto import (
    AuditFixResponse,
    AuditIssue,
    AuditSummary,
    BatchStatus,
    CreatePaymentOrderIn,
    DashboardSummary,
    GSTProfileIn,
    GSTProfileOut,
    GenerateGSTR1In,
    LoginIn,
    IssueLogOut,
    MarketplaceDetectIn,
    MarketplaceDetectResponse,
    RegisterIn,
    ReconcileSettingsIn,
    TallyCompanyIn,
    TallyGenerateIn,
    Token,
    TransactionOut,
    TransactionUpdate,
    VerifyPaymentIn,
)
from app.services.ai_auditor import (
    build_audit_summary,
    detect_marketplace,
    fix_detected_issues,
)
from app.services.billing import (
    create_razorpay_order,
    plan_amount_paise,
    public_plans,
    verify_razorpay_signature,
    verify_razorpay_webhook_signature,
)
from app.services.excel_export import write_gstr1_excel
from app.services.gst import (
    CLEAN_PORTAL,
    GSTTOOL_COMPATIBLE,
    build_gstr1_json,
    document_period,
    gstr1_generation_report,
    normalize_export_mode,
    row_belongs_to_period,
)
from app.services.gsttool_parity_validator import compare_against_reference
from app.services.reconciliation import (
    ReconSettings,
    normalize_rows,
    reconcile,
    write_reconciliation_excel,
)
from app.services.tally import (
    build_tally_xml,
    build_vouchers,
    validate_tally_xml,
    write_voucher_excel,
)
from app.services.transaction_normalizer import finalize_transaction
from app.services.validation import money, validate_gstin, validate_period, validate_transaction
from app.utils.security import create_access_token, hash_password, verify_password

router = APIRouter()
ALLOWED_EXTENSIONS = {".xlsx", ".xlsm", ".xls", ".csv"}
STALE_IMPORT_AFTER = timedelta(minutes=5)
USABLE_IMPORT_STATUSES = {"completed", "completed_with_errors"}

MARKETPLACE_CATALOG = {
    "amazon": {
        "name": "Amazon",
        "category": "Ecommerce",
        "required_files": ["MTR_B2C CSV", "MTR_B2B CSV optional"],
        "guide": "Reports > Manage Taxes > GST Monthly Reports",
    },
    "flipkart": {
        "name": "Flipkart",
        "category": "Ecommerce",
        "required_files": [
            "Sales report Excel",
            "Cash Back report if available",
            "Next month report if needed",
        ],
        "guide": "Reports Center > Tax Reports > Sales report",
    },
    "meesho": {
        "name": "Meesho",
        "category": "Ecommerce",
        "required_files": [
            "tcs_sales.xlsx",
            "tcs_sales_return.xlsx",
            "Tax_invoice_details.xlsx",
        ],
        "guide": "Payments > Download GST Reports",
    },
    "myntra": {
        "name": "Myntra",
        "category": "Ecommerce",
        "required_files": ["Sales report"],
        "guide": "Upload Myntra GST report",
    },
    "jiomart": {
        "name": "JioMart",
        "category": "Ecommerce",
        "required_files": ["Sales report"],
        "guide": "JioMart seller tax report",
    },
    "snapdeal": {
        "name": "Snapdeal",
        "category": "Ecommerce",
        "required_files": ["Sales report"],
        "guide": "Snapdeal tax report",
    },
    "blinkit": {
        "name": "Blinkit",
        "category": "Quick Commerce",
        "required_files": ["Sales report"],
        "guide": "Upload Blinkit seller tax report in the common GST Bharat schema",
    },
    "custom": {
        "name": "Custom Excel",
        "category": "Accounting",
        "required_files": ["Mapped Excel/CSV"],
        "guide": "Use GST Bharat common schema template",
    },
}


def require_valid_period(period: str | None) -> str:
    normalized = str(period or "").strip()
    if not validate_period(normalized):
        raise HTTPException(422, "Invalid filing period")
    return normalized


def dedupe_profiles_by_gstin(profiles: list[GSTProfile]) -> list[GSTProfile]:
    """Return one profile per GSTIN while keeping a deterministic order.

    We preserve the first-seen profile (based on the incoming list order),
    so UI selections using "first profile" stay stable across reloads.
    """
    seen: set[str] = set()
    out: list[GSTProfile] = []
    for profile in profiles:
        key = str(profile.gstin or "").upper()
        if key in seen:
            continue
        seen.add(key)
        out.append(profile)
    return out



def apply_profile_payload(profile: GSTProfile, payload: GSTProfileIn, gstin: str, return_period: str) -> GSTProfile:
    for key, value in payload.model_dump().items():
        setattr(profile, key, value)
    profile.gstin = gstin
    profile.state_code = gstin[:2]
    profile.return_period = return_period
    return profile


def is_super_admin(user: User) -> bool:
    return str(getattr(user, "role", "") or "").lower() == "super_admin"


def enforce_gst_profile_registration_limits(
    user: User,
    db: Session,
    *,
    gstin: str,
    current_profile_id: int | None = None,
) -> None:
    if is_super_admin(user):
        return

    if current_profile_id is None:
        existing_profile = db.scalar(
            select(GSTProfile.id)
            .where(GSTProfile.user_id == user.id)
            .order_by(GSTProfile.id.asc())
        )
        if existing_profile is not None:
            raise HTTPException(
                409,
                "Only one GSTIN can be registered per user account.",
            )

    duplicate_stmt = select(GSTProfile.id).where(GSTProfile.gstin == gstin)
    if current_profile_id is not None:
        duplicate_stmt = duplicate_stmt.where(GSTProfile.id != current_profile_id)
    duplicate_profile = db.scalar(duplicate_stmt.order_by(GSTProfile.id.asc()))
    if duplicate_profile is not None:
        raise HTTPException(
            409,
            "This GSTIN is already registered with another account.",
        )


def paid_until(order: PaymentOrder | None) -> datetime | None:
    if not order or order.status != "paid" or not order.paid_at:
        return None
    days = 365 if order.billing_cycle == "yearly" else 30
    return order.paid_at + timedelta(days=days)


def refresh_subscription(user: User, db: Session) -> tuple[str, str, datetime | None]:
    if getattr(user, "plan", "") == "admin_free" or getattr(user, "role", "") in {
        "admin",
        "super_admin",
    }:
        user.subscription_status = "active"
        db.commit()
        return user.plan, user.subscription_status, None
    latest_paid = db.scalar(
        select(PaymentOrder)
        .where(PaymentOrder.user_id == user.id, PaymentOrder.status == "paid")
        .order_by(PaymentOrder.paid_at.desc(), PaymentOrder.id.desc())
    )
    expires_at = paid_until(latest_paid)
    if latest_paid and expires_at and expires_at > datetime.utcnow():
        user.plan = latest_paid.plan_id
        user.subscription_status = "active"
    else:
        user.subscription_status = "inactive"
    db.commit()
    return (
        getattr(user, "plan", "free"),
        getattr(user, "subscription_status", "inactive"),
        expires_at,
    )


def require_paid_access(
    user: User,
    db: Session,
    required_plan: str | None = None,
) -> None:
    plan, subscription_status, _expires_at = refresh_subscription(user, db)
    if plan == "admin_free" or getattr(user, "role", "") in {"admin", "super_admin"}:
        return
    if subscription_status != "active":
        raise HTTPException(402, "Subscription required")
    if required_plan and plan != required_plan:
        raise HTTPException(403, "This subscription does not include this module")


def settle_paid_order(
    order: PaymentOrder,
    db: Session,
    *,
    payment_id: str | None,
    action: str,
    raw_event: dict | None = None,
) -> User:
    user = db.get(User, order.user_id)
    if not user:
        raise HTTPException(404, "Payment user not found")
    if order.status == "paid":
        if payment_id and not order.provider_payment_id:
            order.provider_payment_id = payment_id
        return user
    order.status = "paid"
    order.provider_payment_id = payment_id or order.provider_payment_id
    order.paid_at = datetime.utcnow()
    if raw_event:
        order.raw_response_json = json.dumps(raw_event)
    user.plan = order.plan_id
    user.subscription_status = "active"
    db.add(
        AuditLog(
            user_id=user.id,
            action=action,
            entity_type="payment_order",
            entity_id=str(order.id),
        )
    )
    return user


def upload_size_bytes(upload: UploadFile) -> int:
    try:
        upload.file.seek(0, 2)
        size = upload.file.tell()
        upload.file.seek(0)
        return int(size)
    except (OSError, AttributeError, ValueError):
        return 0


def enforce_upload_limits(files: list[UploadFile], max_upload_mb: int) -> None:
    max_bytes = max_upload_mb * 1024 * 1024
    total = 0
    for upload in files:
        size = upload_size_bytes(upload)
        total += size
        if size > max_bytes:
            raise HTTPException(
                413,
                f"{upload.filename or 'Upload'} exceeds the {max_upload_mb} MB file limit",
            )
    if total > max_bytes:
        raise HTTPException(413, f"Combined upload exceeds the {max_upload_mb} MB limit")


def settle_stale_import(batch: PlatformImportBatch, db: Session) -> None:
    if batch.status not in {"queued", "processing"}:
        return
    if (
        not batch.created_at
        or datetime.utcnow() - batch.created_at <= STALE_IMPORT_AFTER
    ):
        return
    batch.status = "failed"
    batch.error_report_json = json.dumps(
        [{"error": "Import worker did not complete. Please retry upload."}]
    )
    batch.completed_at = datetime.utcnow()
    db.commit()


def read_import_report(batch: PlatformImportBatch) -> tuple[list[dict], dict]:
    try:
        raw = json.loads(batch.error_report_json or "[]")
    except json.JSONDecodeError:
        return [{"error": batch.error_report_json or "Invalid import report"}], {}
    if isinstance(raw, dict):
        errors = raw.get("parser_errors", [])
        debug = raw.get("debug", {})
        return (errors if isinstance(errors, list) else []), (
            debug if isinstance(debug, dict) else {}
        )
    return (raw if isinstance(raw, list) else []), {}


def validation_summary(transactions: list[dict], parser_errors: list[dict]) -> dict:
    summary = {
        "total_rows": len(transactions),
        "valid_rows": 0,
        "invalid_rows": 0,
        "warning_rows": 0,
        "skipped_rows": 0,
        "unresolved_pos": 0,
        "unsupported_rate": 0,
        "missing_invoice": 0,
        "zero_amount_rows": 0,
        "parser_errors": len(parser_errors),
    }
    for txn in transactions:
        errors = str(txn.get("validation_errors") or "")
        if txn.get("validation_status") == "valid":
            summary["valid_rows"] += 1
        elif txn.get("validation_status") == "skipped":
            summary["skipped_rows"] += 1
        else:
            summary["invalid_rows"] += 1
        if "Missing POS" in errors:
            summary["unresolved_pos"] += 1
        if "Unsupported GST rate" in errors:
            summary["unsupported_rate"] += 1
        if "Missing invoice number" in errors:
            summary["missing_invoice"] += 1
        if "Zero amount row" in errors or "Zero rate and zero taxable row" in errors:
            summary["zero_amount_rows"] += 1
    return summary


AGGREGATE_TRANSACTION_FIELDS = (
    "qty",
    "taxable_value",
    "igst",
    "cgst",
    "sgst",
    "cess",
    "tcs",
    "tds",
    "gross_amount",
    "discount_seller",
    "discount_platform",
    "settlement_amount",
)


def refresh_transaction_validation(txn: dict) -> dict:
    errors = validate_transaction(txn)
    zero_only = errors and all(
        error in {"Zero amount row", "Zero rate and zero taxable row"}
        for error in errors
    )
    txn["validation_status"] = "skipped" if zero_only else "invalid" if errors else "valid"
    txn["validation_errors"] = "; ".join(errors) if errors else None
    return txn


def transaction_import_key(
    profile_id: int,
    txn: dict,
) -> tuple[int, str | None, str | None, str | None, str | None, str | None]:
    return (
        profile_id,
        txn.get("filing_period"),
        txn.get("platform"),
        txn.get("doc_type"),
        txn.get("invoice_no"),
        txn.get("order_item_id"),
    )


def merge_duplicate_transaction(base: dict, incoming: dict) -> dict:
    for field in AGGREGATE_TRANSACTION_FIELDS:
        base[field] = money(base.get(field)) + money(incoming.get(field))

    source_files = [
        source
        for source in [base.get("source_file"), incoming.get("source_file")]
        if source
    ]
    if source_files:
        base["source_file"] = ", ".join(dict.fromkeys(map(str, source_files)))

    base_raw = base.get("raw_row_json")
    incoming_raw = incoming.get("raw_row_json")
    raw_rows = []
    for raw_value in (base_raw, incoming_raw):
        if not raw_value:
            continue
        try:
            parsed = json.loads(raw_value) if isinstance(raw_value, str) else raw_value
        except (TypeError, json.JSONDecodeError):
            parsed = raw_value
        if isinstance(parsed, list):
            raw_rows.extend(parsed)
        else:
            raw_rows.append(parsed)
    if raw_rows:
        base["raw_row_json"] = json.dumps(raw_rows, default=str)

    return refresh_transaction_validation(base)


@router.get("/marketplaces")
def marketplaces():
    items = []
    for key in sorted(PARSERS):
        metadata = MARKETPLACE_CATALOG.get(key, {})
        parser_name = PARSERS[key].__name__
        items.append(
            {
                "key": key,
                "name": metadata.get("name", key.replace("-", " ").title()),
                "category": metadata.get("category", "Accounting"),
                "status": "Active" if parser_name != "CustomExcelParser" or key == "custom" else "Beta",
                "required_files": metadata.get("required_files", ["Sales report"]),
                "guide": metadata.get("guide", "Upload marketplace report"),
                "parser": parser_name,
            }
        )
    return {"marketplaces": items}


def batch_status_response(batch: PlatformImportBatch) -> BatchStatus:
    parser_errors, debug = read_import_report(batch)
    return BatchStatus(
        id=batch.id,
        platform=batch.platform,
        period=batch.period,
        status=batch.status,
        parsed_rows=batch.parsed_rows,
        error_rows=batch.error_rows,
        errors=parser_errors,
        debug=debug,
    )


def stored_import_paths(batch: PlatformImportBatch, db: Session) -> list[str]:
    uploads = db.scalars(
        select(UploadedFile)
        .where(UploadedFile.batch_id == batch.id, UploadedFile.user_id == batch.user_id)
        .order_by(UploadedFile.id.asc())
    ).all()
    paths = [uploaded.stored_path for uploaded in uploads if uploaded.stored_path]
    missing = [path for path in paths if not Path(path).exists()]
    if missing:
        raise FileNotFoundError(f"Uploaded source file missing: {missing[0]}")
    return paths


def period_from_document_date(value: object) -> str | None:
    try:
        parsed = datetime.fromisoformat(str(value)).date()
    except (TypeError, ValueError):
        return None
    return f"{parsed.month:02d}{parsed.year}"


def dominant_excluded_period(result) -> str | None:
    rows = result.debug.get("period_excluded_rows", [])
    periods = [
        period
        for period in (
            period_from_document_date(row.get("document_date"))
            for row in rows
            if isinstance(row, dict)
        )
        if period
    ]
    if not periods:
        return None
    [(period, count)] = Counter(periods).most_common(1)
    return period if count == len(periods) else None


def clear_batch_transactions(batch: PlatformImportBatch, db: Session) -> None:
    rows = db.scalars(
        select(NormalizedTransaction).where(
            NormalizedTransaction.batch_id == batch.id,
            NormalizedTransaction.user_id == batch.user_id,
        )
    ).all()
    for row in rows:
        db.delete(row)
    db.flush()


def clear_platform_period_transactions(batch: PlatformImportBatch, db: Session) -> int:
    rows = db.scalars(
        select(NormalizedTransaction).where(
            NormalizedTransaction.user_id == batch.user_id,
            NormalizedTransaction.profile_id == batch.profile_id,
            NormalizedTransaction.filing_period == batch.period,
            NormalizedTransaction.platform == batch.platform,
        )
    ).all()
    for row in rows:
        db.delete(row)
    db.flush()
    return len(rows)


def clear_uploaded_files_for_profile_period(
    user_id: int,
    profile_id: int,
    period: str,
    db: Session,
) -> int:
    batches = db.scalars(
        select(PlatformImportBatch).where(
            PlatformImportBatch.user_id == user_id,
            PlatformImportBatch.profile_id == profile_id,
            PlatformImportBatch.period == period,
        )
    ).all()
    if not batches:
        return 0
    batch_ids = [batch.id for batch in batches]
    files = db.scalars(
        select(UploadedFile).where(
            UploadedFile.user_id == user_id,
            UploadedFile.batch_id.in_(batch_ids),
        )
    ).all()
    removed = 0
    cleaned_dirs: set[Path] = set()
    for uploaded in files:
        if uploaded.stored_path:
            path = Path(uploaded.stored_path)
            try:
                path.unlink(missing_ok=True)
                cleaned_dirs.add(path.parent)
            except OSError:
                pass
        db.delete(uploaded)
        removed += 1
    for directory in cleaned_dirs:
        try:
            if directory.exists() and not any(directory.iterdir()):
                shutil.rmtree(directory, ignore_errors=True)
        except OSError:
            pass
    db.flush()
    return removed


def transaction_row_import_is_usable(row: NormalizedTransaction, db: Session) -> bool:
    if row.batch_id is None:
        return True
    batch = db.get(PlatformImportBatch, row.batch_id)
    return bool(batch and batch.status in USABLE_IMPORT_STATUSES)


def usable_transaction_rows(
    rows: list[NormalizedTransaction],
    db: Session,
) -> list[NormalizedTransaction]:
    batch_ids = sorted({row.batch_id for row in rows if row.batch_id is not None})
    if not batch_ids:
        return rows
    batches = db.scalars(
        select(PlatformImportBatch).where(PlatformImportBatch.id.in_(batch_ids))
    ).all()
    statuses = {batch.id: batch.status for batch in batches}
    return [
        row
        for row in rows
        if row.batch_id is None or statuses.get(row.batch_id) in USABLE_IMPORT_STATUSES
    ]


@router.post("/auth/register", response_model=Token)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    existing = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing:
        raise HTTPException(409, "Email is already registered")
    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return Token(access_token=create_access_token(str(user.id)))


@router.post("/auth/login", response_model=Token)
def login(payload: LoginIn, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(401, "Invalid email or password")
    return Token(access_token=create_access_token(str(user.id)))


@router.get("/auth/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plan, subscription_status, expires_at = refresh_subscription(user, db)
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": getattr(user, "role", "user"),
        "plan": plan,
        "subscription_status": subscription_status,
        "subscription_expires_at": expires_at,
        "free_access_reason": getattr(user, "free_access_reason", None),
    }


@router.get("/billing/plans")
def billing_plans(user: User = Depends(get_current_user)):
    return {
        "plans": public_plans(),
        "gateway": "razorpay",
        "free_access": getattr(user, "plan", "") == "admin_free",
    }


@router.get("/billing/status")
def billing_status(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    latest = db.scalar(
        select(PaymentOrder)
        .where(PaymentOrder.user_id == user.id)
        .order_by(PaymentOrder.id.desc())
    )
    plan, subscription_status, expires_at = refresh_subscription(user, db)
    return {
        "role": getattr(user, "role", "user"),
        "plan": plan,
        "subscription_status": subscription_status,
        "subscription_expires_at": expires_at,
        "free_access": getattr(user, "plan", "") == "admin_free",
        "free_access_reason": getattr(user, "free_access_reason", None),
        "latest_order": (
            {
                "id": latest.id,
                "plan_id": latest.plan_id,
                "billing_cycle": latest.billing_cycle,
                "amount": latest.amount_paise / 100,
                "status": latest.status,
                "provider_order_id": latest.provider_order_id,
            }
            if latest
            else None
        ),
    }


@router.post("/billing/create-order")
def create_payment_order(
    payload: CreatePaymentOrderIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if getattr(user, "plan", "") == "admin_free":
        return {
            "free_access": True,
            "message": "This admin account has unrestricted free access.",
            "plan": user.plan,
            "subscription_status": user.subscription_status,
        }
    try:
        amount_paise = plan_amount_paise(payload.plan_id, payload.billing_cycle)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    order = PaymentOrder(
        user_id=user.id,
        plan_id=payload.plan_id,
        billing_cycle=payload.billing_cycle,
        amount_paise=amount_paise,
        currency="INR",
    )
    db.add(order)
    db.flush()
    settings = get_settings()
    try:
        gateway_order = create_razorpay_order(
            settings, amount_paise, f"gstbharat_{order.id}"
        )
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from exc
    order.provider_order_id = str(gateway_order.get("id"))
    order.raw_response_json = json.dumps(gateway_order)
    db.add(
        AuditLog(
            user_id=user.id,
            action="billing.order.create",
            entity_type="payment_order",
            entity_id=str(order.id),
            metadata_json=json.dumps(
                {"plan_id": payload.plan_id, "billing_cycle": payload.billing_cycle}
            ),
        )
    )
    db.commit()
    db.refresh(order)
    return {
        "id": order.id,
        "provider": "razorpay",
        "provider_order_id": order.provider_order_id,
        "amount": order.amount_paise / 100,
        "amount_paise": order.amount_paise,
        "currency": order.currency,
        "plan_id": order.plan_id,
        "billing_cycle": order.billing_cycle,
        "gateway_key_id": settings.razorpay_key_id,
        "gateway_configured": bool(
            settings.razorpay_key_id and settings.razorpay_key_secret
        ),
    }


@router.post("/billing/verify")
def verify_payment(
    payload: VerifyPaymentIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    order = db.get(PaymentOrder, payload.order_id)
    if not order or order.user_id != user.id:
        raise HTTPException(404, "Payment order not found")
    if order.provider_order_id != payload.razorpay_order_id:
        raise HTTPException(422, "Razorpay order ID mismatch")
    settings = get_settings()
    if not verify_razorpay_signature(
        settings,
        payload.razorpay_order_id,
        payload.razorpay_payment_id,
        payload.razorpay_signature,
    ):
        raise HTTPException(422, "Invalid payment signature")
    settle_paid_order(
        order,
        db,
        payment_id=payload.razorpay_payment_id,
        action="billing.payment.verified",
    )
    db.commit()
    return {
        "status": "paid",
        "plan": user.plan,
        "subscription_status": user.subscription_status,
        "subscription_expires_at": paid_until(order),
    }


@router.post("/billing/razorpay/webhook")
async def razorpay_webhook(
    request: Request,
    x_razorpay_signature: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    body = await request.body()
    settings = get_settings()
    if not verify_razorpay_webhook_signature(settings, body, x_razorpay_signature):
        raise HTTPException(401, "Invalid webhook signature")
    try:
        event = json.loads(body.decode())
    except json.JSONDecodeError as exc:
        raise HTTPException(422, "Invalid webhook payload") from exc

    event_name = str(event.get("event") or "")
    payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
    payment = (
        payload.get("payment", {}).get("entity")
        if isinstance(payload.get("payment"), dict)
        else None
    )
    order_entity = (
        payload.get("order", {}).get("entity")
        if isinstance(payload.get("order"), dict)
        else None
    )
    provider_order_id = None
    payment_id = None
    paid_amount = None

    if isinstance(payment, dict):
        provider_order_id = payment.get("order_id")
        payment_id = payment.get("id")
        paid_amount = payment.get("amount")
    if not provider_order_id and isinstance(order_entity, dict):
        provider_order_id = order_entity.get("id")
        paid_amount = order_entity.get("amount_paid") or order_entity.get("amount")

    if not provider_order_id:
        return {"status": "ignored", "reason": "no_order_id"}
    if event_name not in {"payment.captured", "order.paid"}:
        return {"status": "ignored", "event": event_name}

    order = db.scalar(
        select(PaymentOrder).where(PaymentOrder.provider_order_id == str(provider_order_id))
    )
    if not order:
        return {"status": "ignored", "reason": "unknown_order"}
    if paid_amount is not None and int(paid_amount) < int(order.amount_paise):
        raise HTTPException(422, "Webhook amount is lower than order amount")

    settle_paid_order(
        order,
        db,
        payment_id=str(payment_id) if payment_id else None,
        action="billing.payment.webhook",
        raw_event=event,
    )
    db.commit()
    return {"status": "processed", "order_id": order.id}


@router.post("/gst-profile", response_model=GSTProfileOut)
def create_profile(
    payload: GSTProfileIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    gstin = payload.gstin.upper()
    if not validate_gstin(gstin):
        raise HTTPException(422, "Invalid GSTIN")
    return_period = require_valid_period(payload.return_period)
    existing_same_gstin_profile = db.scalar(
        select(GSTProfile)
        .where(GSTProfile.user_id == user.id, GSTProfile.gstin == gstin)
        .order_by(GSTProfile.id.asc())
    )
    if existing_same_gstin_profile:
        apply_profile_payload(existing_same_gstin_profile, payload, gstin, return_period)
        db.add(
            AuditLog(
                user_id=user.id,
                action="gst_profile.update_same_gstin",
                entity_type="gst_profile",
                entity_id=str(existing_same_gstin_profile.id),
            )
        )
        db.commit()
        db.refresh(existing_same_gstin_profile)
        return existing_same_gstin_profile
    enforce_gst_profile_registration_limits(user, db, gstin=gstin)
    profile = GSTProfile(
        user_id=user.id,
        gstin=gstin,
        legal_name=payload.legal_name,
        trade_name=payload.trade_name,
        state_code=gstin[:2],
        filing_frequency=payload.filing_frequency,
        financial_year=payload.financial_year,
        return_period=return_period,
    )
    db.add(profile)
    db.add(
        AuditLog(
            user_id=user.id, action="gst_profile.create", entity_type="gst_profile"
        )
    )
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/gst-profile", response_model=list[GSTProfileOut])
def list_profiles(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    if is_super_admin(user):
        profiles = db.scalars(
            select(GSTProfile).order_by(GSTProfile.user_id.asc(), GSTProfile.id.asc())
        ).all()
        return dedupe_profiles_by_gstin(profiles)
    profiles = db.scalars(
        select(GSTProfile).where(GSTProfile.user_id == user.id).order_by(GSTProfile.id.asc())
    ).all()
    return dedupe_profiles_by_gstin(profiles)


@router.post("/demo/seed")
def seed_demo(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.scalar(
        select(GSTProfile)
        .where(GSTProfile.user_id == user.id)
        .order_by(GSTProfile.id.asc())
    )
    if not profile:
        profile = GSTProfile(
            user_id=user.id,
            gstin="07ABCDE1234F1Z5",
            legal_name="Bharat Online Traders",
            trade_name="Bharat Store",
            state_code="07",
            filing_frequency="Monthly",
            financial_year="2026-27",
            return_period="042026",
        )
        db.add(profile)
        db.flush()
    existing = db.scalars(
        select(NormalizedTransaction).where(
            NormalizedTransaction.user_id == user.id,
            NormalizedTransaction.profile_id == profile.id,
        )
    ).all()
    if existing:
        return {
            "profile_id": profile.id,
            "transactions": len(existing),
            "status": "already_seeded",
        }
    batch = PlatformImportBatch(
        user_id=user.id,
        profile_id=profile.id,
        period=profile.return_period,
        platform="demo",
        status="completed",
        parsed_rows=6,
        error_rows=0,
        completed_at=datetime.utcnow(),
    )
    db.add(batch)
    db.flush()
    rows = [
        {
            "platform": "meesho",
            "etin": "07AARCM9332R1CQ",
            "order_id": "MSH-1001",
            "order_item_id": "1",
            "invoice_no": "MSH-28491",
            "invoice_date": "2026-04-04",
            "buyer_state_code": "37",
            "buyer_state_name": "Andhra Pradesh",
            "hsn": "711790",
            "product_name": "Fashion jewellery set",
            "sku": "JWL-01",
            "qty": 1,
            "taxable_value": 1327.42,
            "gst_rate": 3,
            "igst": 39.82,
            "tcs": 13.27,
            "source_file": "tcs_sales.xlsx",
        },
        {
            "platform": "amazon",
            "etin": "29AAICA3918J1C9",
            "order_id": "405-1122",
            "order_item_id": "A1",
            "invoice_no": "IN-7781",
            "invoice_date": "2026-04-08",
            "buyer_state_code": "07",
            "buyer_state_name": "Delhi",
            "hsn": "7117",
            "product_name": "Oxidised necklace",
            "sku": "AMZ-JW-2",
            "qty": 2,
            "taxable_value": 2600,
            "gst_rate": 3,
            "cgst": 39,
            "sgst": 39,
            "tcs": 26,
            "source_file": "MTR_B2C.csv",
        },
        {
            "platform": "flipkart",
            "etin": "29AACCF0683K1C8",
            "order_id": "OD3301",
            "order_item_id": "FK1",
            "invoice_no": "FK-9982",
            "invoice_date": "2026-04-12",
            "buyer_state_code": "29",
            "buyer_state_name": "Karnataka",
            "hsn": "4202",
            "product_name": "Travel pouch",
            "sku": "FK-BAG-1",
            "qty": 1,
            "taxable_value": 4100,
            "gst_rate": 18,
            "igst": 738,
            "tcs": 41,
            "source_file": "sales-report.xlsx:hidden",
        },
        {
            "platform": "meesho",
            "etin": "07AARCM9332R1CQ",
            "order_id": "MSH-1001",
            "order_item_id": "1-R",
            "invoice_no": "CN-120",
            "invoice_date": "2026-04-16",
            "doc_type": "credit_note",
            "buyer_state_code": "37",
            "buyer_state_name": "Andhra Pradesh",
            "hsn": "711790",
            "product_name": "Fashion jewellery set",
            "sku": "JWL-01",
            "qty": 1,
            "taxable_value": 420,
            "gst_rate": 3,
            "igst": 12.6,
            "tcs": 4.2,
            "source_file": "tcs_sales_return.xlsx",
        },
        {
            "platform": "jiomart",
            "etin": "27AABCI6363G1C7",
            "order_id": "JM-901",
            "order_item_id": "J1",
            "invoice_no": "JM-551",
            "invoice_date": "2026-04-18",
            "buyer_state_code": "24",
            "buyer_state_name": "Gujarat",
            "hsn": "3926",
            "product_name": "Home organizer",
            "sku": "ORG-9",
            "qty": 4,
            "taxable_value": 1199.2,
            "gst_rate": 18,
            "igst": 215.86,
            "source_file": "jiomart-sales.xlsx",
        },
        {
            "platform": "custom",
            "etin": "29AACCF0683K1C8",
            "order_id": "CUS-18",
            "order_item_id": "C1",
            "invoice_no": "CUST-18",
            "invoice_date": "2026-04-21",
            "buyer_state_code": "07",
            "buyer_state_name": "Delhi",
            "hsn": "4819",
            "product_name": "Packaging material",
            "sku": "PACK-1",
            "qty": 10,
            "taxable_value": 850,
            "gst_rate": 12,
            "cgst": 51,
            "sgst": 51,
            "source_file": "custom.xlsx",
        },
    ]
    for row in rows:
        row = dict(row)
        txn = finalize_transaction(
            {
                "gstin": profile.gstin,
                "filing_period": profile.return_period,
                "doc_type": row.pop("doc_type", "invoice"),
                "cess": 0,
                "tds": 0,
                "gross_amount": 0,
                "discount_seller": 0,
                "discount_platform": 0,
                "settlement_amount": 0,
                "raw_row_json": json.dumps(row, default=str),
                **row,
            }
        )
        db.add(
            NormalizedTransaction(
                user_id=user.id, profile_id=profile.id, batch_id=batch.id, **txn
            )
        )
    db.add(
        AuditLog(
            user_id=user.id,
            action="demo.seed",
            entity_type="gst_profile",
            entity_id=str(profile.id),
        )
    )
    db.commit()
    return {"profile_id": profile.id, "transactions": len(rows), "status": "seeded"}


@router.put("/gst-profile/{profile_id}", response_model=GSTProfileOut)
def update_profile(
    profile_id: int,
    payload: GSTProfileIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.get(GSTProfile, profile_id)
    if not profile or profile.user_id != user.id:
        raise HTTPException(404, "Profile not found")
    gstin = payload.gstin.upper()
    if not validate_gstin(gstin):
        raise HTTPException(422, "Invalid GSTIN")
    return_period = require_valid_period(payload.return_period)
    enforce_gst_profile_registration_limits(
        user,
        db,
        gstin=gstin,
        current_profile_id=profile.id,
    )
    apply_profile_payload(profile, payload, gstin, return_period)
    db.commit()
    db.refresh(profile)
    return profile


@router.post("/imports/{platform}/upload", response_model=BatchStatus)
async def upload_import(
    platform: str,
    background_tasks: BackgroundTasks,
    profile_id: int,
    files: list[UploadFile] = File(...),
    period: str | None = None,
    required_plan: str | None = "online_seller",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_paid_access(user, db, required_plan)
    profile = db.get(GSTProfile, profile_id)
    if not profile or profile.user_id != user.id:
        raise HTTPException(404, "Profile not found")
    import_period = require_valid_period(period or profile.return_period)
    platform_key = platform.lower()
    if platform_key not in PARSERS:
        raise HTTPException(422, f"Unsupported platform: {platform}")
    if not files:
        raise HTTPException(422, "At least one file is required")
    for upload in files:
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(422, f"Unsupported file type: {upload.filename}")
    settings = get_settings()
    enforce_upload_limits(files, settings.max_upload_mb)
    batch = PlatformImportBatch(
        user_id=user.id,
        profile_id=profile.id,
        period=import_period,
        platform=platform_key,
        status="queued",
    )
    db.add(batch)
    db.flush()
    stored_paths: list[Path] = []
    for upload in files:
        suffix = Path(upload.filename or "").suffix.lower()
        stored = (
            settings.upload_dir
            / str(user.id)
            / str(batch.id)
            / f"{uuid4().hex}{suffix}"
        )
        stored.parent.mkdir(parents=True, exist_ok=True)
        with stored.open("wb") as handle:
            shutil.copyfileobj(upload.file, handle)
        stored_paths.append(stored)
        db.add(
            UploadedFile(
                batch_id=batch.id,
                user_id=user.id,
                original_name=upload.filename or stored.name,
                stored_path=str(stored),
                content_type=upload.content_type,
                size_bytes=stored.stat().st_size,
            )
        )
    db.add(
        AuditLog(
            user_id=user.id,
            action="import.upload",
            entity_type="platform_import_batch",
            entity_id=str(batch.id),
            metadata_json=json.dumps({"platform": platform, "period": import_period}),
        )
    )
    db.commit()
    background_tasks.add_task(
        process_import_batch, batch.id, [str(path) for path in stored_paths]
    )
    return BatchStatus(
        id=batch.id,
        platform=batch.platform,
        period=batch.period,
        status=batch.status,
        parsed_rows=0,
        error_rows=0,
    )


def run_import_parser(
    batch: PlatformImportBatch,
    file_paths: list[str],
    db: Session,
    *,
    replace_existing_batch_rows: bool = False,
) -> PlatformImportBatch:
    profile = db.get(GSTProfile, batch.profile_id)
    if not profile:
        raise RuntimeError("GST profile for import batch no longer exists")

    batch.status = "processing"
    batch.error_rows = 0
    batch.error_report_json = None
    db.commit()

    if replace_existing_batch_rows:
        clear_batch_transactions(batch, db)

    parser = get_parser(batch.platform)(
        profile.gstin,
        batch.period or profile.return_period,
    )
    result = parser.parse([Path(path) for path in file_paths])
    detected_period = dominant_excluded_period(result)
    if (
        not result.transactions
        and detected_period
        and detected_period != (batch.period or profile.return_period)
    ):
        original_period = batch.period or profile.return_period
        batch.period = detected_period
        profile.return_period = detected_period
        parser = get_parser(batch.platform)(profile.gstin, detected_period)
        reparsed = parser.parse([Path(path) for path in file_paths])
        reparsed.debug["auto_period_switch"] = {
            "from": original_period,
            "to": detected_period,
            "reason": "All parsed document dates were outside the selected filing period.",
        }
        result = reparsed
    aggregated_transactions: dict[
        tuple[int, str | None, str | None, str | None, str | None, str | None],
        dict,
    ] = {}
    duplicate_rows: list[dict] = []
    for txn in result.transactions:
        txn = dict(txn)
        txn["filing_period"] = (
            txn.get("filing_period")
            or document_period(txn)
            or batch.period
            or profile.return_period
        )
        key = transaction_import_key(batch.profile_id, txn)
        if key in aggregated_transactions:
            merge_duplicate_transaction(aggregated_transactions[key], txn)
            duplicate_rows.append(
                {
                    "filing_period": key[1],
                    "platform": key[2],
                    "doc_type": key[3],
                    "invoice_no": key[4],
                    "order_item_id": key[5],
                }
            )
        else:
            aggregated_transactions[key] = txn

    if duplicate_rows:
        result.debug["aggregated_duplicate_rows"] = duplicate_rows

    replaced_rows = clear_platform_period_transactions(batch, db)
    if replaced_rows:
        result.debug["replaced_platform_period_rows"] = replaced_rows

    inserted_rows = 0
    validation_error_rows = 0

    for key, txn in aggregated_transactions.items():
        existing = db.scalar(
            select(NormalizedTransaction).where(
                NormalizedTransaction.profile_id == key[0],
                NormalizedTransaction.filing_period == key[1],
                NormalizedTransaction.platform == key[2],
                NormalizedTransaction.doc_type == key[3],
                NormalizedTransaction.invoice_no == key[4],
                NormalizedTransaction.order_item_id == key[5],
            )
        )
        if existing and not transaction_row_import_is_usable(existing, db):
            db.delete(existing)
            db.flush()
            existing = None
        if existing is not None:
            continue
        db.add(
            NormalizedTransaction(
                user_id=batch.user_id,
                profile_id=batch.profile_id,
                batch_id=batch.id,
                **txn,
            )
        )
        inserted_rows += 1
        validation_error_rows += (
            1 if txn.get("validation_status") in {"error", "invalid"} else 0
        )

    batch.parsed_rows = inserted_rows
    batch.error_rows = len(result.errors) + validation_error_rows
    result.debug["validation_summary"] = validation_summary(
        list(aggregated_transactions.values()), result.errors
    )
    batch.error_report_json = json.dumps(
        {"parser_errors": result.errors, "debug": result.debug},
        default=str,
    )
    batch.status = "completed" if batch.error_rows == 0 else "completed_with_errors"
    batch.completed_at = datetime.utcnow()
    return batch


def process_import_batch(batch_id: int, file_paths: list[str]):
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        batch = db.get(PlatformImportBatch, batch_id)
        if not batch:
            return
        run_import_parser(batch, file_paths, db)
        db.add(
            AuditLog(
                user_id=batch.user_id,
                action="import.processed",
                entity_type="platform_import_batch",
                entity_id=str(batch.id),
            )
        )
        db.commit()
    except Exception as exc:
        db.rollback()
        try:
            batch = db.get(PlatformImportBatch, batch_id)
            if batch:
                clear_batch_transactions(batch, db)
                batch.parsed_rows = 0
                batch.status = "failed"
                batch.error_report_json = json.dumps([{"error": str(exc)}])
                db.commit()
        except Exception:
            db.rollback()
    finally:
        db.close()


@router.get("/imports/{batch_id}/status", response_model=BatchStatus)
def import_status(
    batch_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    batch = db.get(PlatformImportBatch, batch_id)
    if not batch or batch.user_id != user.id:
        raise HTTPException(404, "Batch not found")
    settle_stale_import(batch, db)
    return batch_status_response(batch)


@router.post("/imports/{batch_id}/reprocess", response_model=BatchStatus)
def reprocess_import_batch(
    batch_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_paid_access(user, db)
    batch = db.get(PlatformImportBatch, batch_id)
    if not batch or batch.user_id != user.id:
        raise HTTPException(404, "Batch not found")
    settle_stale_import(batch, db)
    if batch.status in {"queued", "processing"}:
        raise HTTPException(409, "Import is still processing")

    try:
        paths = stored_import_paths(batch, db)
        run_import_parser(batch, paths, db, replace_existing_batch_rows=True)
        db.add(
            AuditLog(
                user_id=user.id,
                action="import.reprocess",
                entity_type="platform_import_batch",
                entity_id=str(batch.id),
            )
        )
        db.commit()
        db.refresh(batch)
        return batch_status_response(batch)
    except FileNotFoundError as exc:
        db.rollback()
        raise HTTPException(404, str(exc)) from exc
    except Exception as exc:
        db.rollback()
        try:
            batch = db.get(PlatformImportBatch, batch_id)
            if batch:
                batch.status = "failed"
                clear_batch_transactions(batch, db)
                batch.parsed_rows = 0
                batch.error_report_json = json.dumps([{"error": str(exc)}])
                batch.completed_at = datetime.utcnow()
                db.commit()
        except Exception:
            db.rollback()
        raise HTTPException(500, str(exc)) from exc


@router.get("/imports", response_model=list[BatchStatus])
def list_imports(
    profile_id: int | None = None,
    period: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = (
        select(PlatformImportBatch)
        .where(PlatformImportBatch.user_id == user.id)
        .order_by(PlatformImportBatch.id.desc())
    )
    if profile_id:
        stmt = stmt.where(PlatformImportBatch.profile_id == profile_id)
    if period:
        stmt = stmt.where(PlatformImportBatch.period == period)
    batches = db.scalars(stmt.limit(50)).all()
    for batch in batches:
        settle_stale_import(batch, db)
    return [
        batch_status_response(batch)
        for batch in batches
    ]


@router.get("/imports/{batch_id}/errors")
def import_errors(
    batch_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    batch = db.get(PlatformImportBatch, batch_id)
    if not batch or batch.user_id != user.id:
        raise HTTPException(404, "Batch not found")
    parser_errors, debug = read_import_report(batch)
    rows = db.scalars(
        select(NormalizedTransaction).where(
            NormalizedTransaction.batch_id == batch_id,
            NormalizedTransaction.validation_status.in_(
                ["error", "invalid", "warning", "skipped"]
            ),
        )
    ).all()
    row_errors = []
    for row in rows:
        item = TransactionOut.model_validate(row).model_dump(mode="json")
        reason = item.get("validation_errors") or "Validation failed"
        item["reason"] = reason
        item["suggested_fix"] = (
            "Map or enter buyer POS/state"
            if "Missing POS" in reason
            else (
                "Map invoice/document number column"
                if "Missing invoice number" in reason
                else (
                    "Check GST rate/taxable/tax columns"
                    if "GST rate" in reason or "Tax mismatch" in reason
                    else "Review source row and correct normalized values"
                )
            )
        )
        item["raw_column_source"] = item.get("source_file")
        item["pos_resolution_source"] = (
            "buyer_state_code" if item.get("buyer_state_code") else "unresolved"
        )
        item["gst_rate_resolution_source"] = (
            "normalized_gst_rate" if item.get("gst_rate") else "unresolved"
        )
        row_errors.append(item)
    return {
        "parser_errors": parser_errors,
        "parser_debug": debug,
        "row_errors": row_errors,
        "actions": [
            "fix POS manually",
            "map column",
            "correct GST rate",
            "reprocess batch",
            "export error report",
        ],
    }


@router.delete("/imports/{batch_id}")
def delete_import_batch(
    batch_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    require_paid_access(user, db)
    batch = db.get(PlatformImportBatch, batch_id)
    if not batch or batch.user_id != user.id:
        raise HTTPException(404, "Batch not found")
    settle_stale_import(batch, db)
    if batch.status in {"queued", "processing"}:
        raise HTTPException(409, "Import is still processing")

    files = db.scalars(
        select(UploadedFile).where(
            UploadedFile.batch_id == batch.id, UploadedFile.user_id == user.id
        )
    ).all()
    stored_paths = [uploaded.stored_path for uploaded in files if uploaded.stored_path]
    for txn in db.scalars(
        select(NormalizedTransaction).where(
            NormalizedTransaction.batch_id == batch.id,
            NormalizedTransaction.user_id == user.id,
        )
    ).all():
        db.delete(txn)
    for uploaded in files:
        db.delete(uploaded)
    db.add(
        AuditLog(
            user_id=user.id,
            action="import.delete",
            entity_type="platform_import_batch",
            entity_id=str(batch.id),
        )
    )
    db.delete(batch)
    db.commit()

    for stored_path in stored_paths:
        path = Path(stored_path)
        if path.exists():
            path.unlink()
        parent = path.parent
        if parent.exists() and not any(parent.iterdir()):
            shutil.rmtree(parent, ignore_errors=True)
    return {"ok": True}


@router.get("/transactions", response_model=list[TransactionOut])
def transactions(
    profile_id: int | None = None,
    period: str | None = None,
    platform: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(NormalizedTransaction).where(NormalizedTransaction.user_id == user.id)
    if profile_id:
        stmt = stmt.where(NormalizedTransaction.profile_id == profile_id)
    if platform:
        stmt = stmt.where(NormalizedTransaction.platform == platform)
    rows = usable_transaction_rows(db.scalars(stmt).all(), db)
    if period:
        rows = [row for row in rows if transaction_matches_period(row, period)]
    return rows[:1000]


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(
    profile_id: int | None = None,
    period: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(NormalizedTransaction).where(NormalizedTransaction.user_id == user.id)
    if profile_id:
        stmt = stmt.where(NormalizedTransaction.profile_id == profile_id)
    rows = usable_transaction_rows(db.scalars(stmt).all(), db)
    if period:
        rows = [row for row in rows if transaction_matches_period(row, period)]
    platform_totals: dict[str, dict] = {}
    state_totals: dict[str, dict] = {}
    total_taxable = money(0)
    total_sales = money(0)
    igst = money(0)
    cgst = money(0)
    sgst = money(0)
    pending_errors = 0
    for row in rows:
        taxable = money(row.taxable_value)
        row_gst = money(row.igst) + money(row.cgst) + money(row.sgst) + money(row.cess)
        total_taxable += taxable
        total_sales += taxable + row_gst
        igst += money(row.igst)
        cgst += money(row.cgst)
        sgst += money(row.sgst)
        pending_errors += 1 if row.validation_status in {"error", "invalid"} else 0
        platform = row.platform or "unknown"
        state = row.buyer_state_code or "NA"
        platform_totals.setdefault(
            platform,
            {
                "platform": platform,
                "taxable_value": money(0),
                "gst": money(0),
                "rows": 0,
            },
        )
        state_totals.setdefault(
            state,
            {
                "state_code": state,
                "taxable_value": money(0),
                "gst": money(0),
                "rows": 0,
            },
        )
        platform_totals[platform]["taxable_value"] += taxable
        platform_totals[platform]["gst"] += row_gst
        platform_totals[platform]["rows"] += 1
        state_totals[state]["taxable_value"] += taxable
        state_totals[state]["gst"] += row_gst
        state_totals[state]["rows"] += 1
    uploaded_file_stmt = select(UploadedFile).where(UploadedFile.user_id == user.id)
    uploaded_files = len(db.scalars(uploaded_file_stmt).all())
    export_stmt = select(GSTR1JsonExport).where(GSTR1JsonExport.user_id == user.id)
    if profile_id:
        export_stmt = export_stmt.where(GSTR1JsonExport.profile_id == profile_id)
    if period:
        export_stmt = export_stmt.where(GSTR1JsonExport.period == period)
    latest_export = db.scalar(export_stmt.order_by(GSTR1JsonExport.id.desc()))
    audit_summary = None
    if rows:
        profile = None
        if profile_id:
            profile = db.get(GSTProfile, profile_id)
        else:
            profile = db.get(GSTProfile, rows[0].profile_id)
        if profile:
            audit_summary = build_audit_summary(rows, profile)
    return DashboardSummary(
        total_sales=money(total_sales),
        total_taxable_value=money(total_taxable),
        total_gst=money(igst + cgst + sgst),
        igst=money(igst),
        cgst=money(cgst),
        sgst=money(sgst),
        platform_wise_sale=[
            {
                **item,
                "taxable_value": money(item["taxable_value"]),
                "gst": money(item["gst"]),
            }
            for item in platform_totals.values()
        ],
        state_wise_sale=[
            {
                **item,
                "taxable_value": money(item["taxable_value"]),
                "gst": money(item["gst"]),
            }
            for item in state_totals.values()
        ],
        uploaded_files=uploaded_files,
        pending_errors=pending_errors,
        json_generation_status=(
            latest_export.status if latest_export else "not_generated"
        ),
        auditor_health_score=audit_summary["auditor_health_score"] if audit_summary else None,
        auditor_risk_score=audit_summary["auditor_risk_score"] if audit_summary else None,
        readiness_status=audit_summary["readiness_status"] if audit_summary else None,
        auditor_warnings=audit_summary["warnings"] if audit_summary else None,
        auditor_issue_counts=audit_summary["issue_counts"] if audit_summary else None,
    )


@router.get("/auditor/summary", response_model=AuditSummary)
def auditor_summary(
    profile_id: int | None = None,
    period: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(NormalizedTransaction).where(NormalizedTransaction.user_id == user.id)
    if profile_id:
        stmt = stmt.where(NormalizedTransaction.profile_id == profile_id)
    rows = usable_transaction_rows(db.scalars(stmt).all(), db)
    if period:
        rows = [row for row in rows if transaction_matches_period(row, period)]
    if not rows:
        raise HTTPException(404, "No transactions found for audit summary")
    profile = db.get(GSTProfile, profile_id) if profile_id else db.get(GSTProfile, rows[0].profile_id)
    if not profile:
        raise HTTPException(404, "GST profile not found for audit summary")
    summary = build_audit_summary(rows, profile)
    return AuditSummary(
        profile_id=profile.id,
        period=period,
        auditor_health_score=summary["auditor_health_score"],
        auditor_risk_score=summary["auditor_risk_score"],
        readiness_status=summary["readiness_status"],
        issue_counts=summary["issue_counts"],
        warnings=summary["warnings"],
        details=summary["details"],
    )


@router.get("/auditor/issues", response_model=list[AuditIssue])
def auditor_issues(
    profile_id: int | None = None,
    period: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(NormalizedTransaction).where(NormalizedTransaction.user_id == user.id)
    if profile_id:
        stmt = stmt.where(NormalizedTransaction.profile_id == profile_id)
    rows = usable_transaction_rows(db.scalars(stmt).all(), db)
    if period:
        rows = [row for row in rows if transaction_matches_period(row, period)]
    if not rows:
        return []
    profile = db.get(GSTProfile, profile_id) if profile_id else db.get(GSTProfile, rows[0].profile_id)
    if not profile:
        return []
    summary = build_audit_summary(rows, profile)
    return [AuditIssue(**issue) for issue in summary["details"]]


@router.post("/auditor/fix", response_model=AuditFixResponse)
def auditor_fix(
    profile_id: int | None = None,
    period: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_paid_access(user, db, required_plan="online_seller")
    stmt = select(NormalizedTransaction).where(NormalizedTransaction.user_id == user.id)
    if profile_id:
        stmt = stmt.where(NormalizedTransaction.profile_id == profile_id)
    rows = usable_transaction_rows(db.scalars(stmt).all(), db)
    if period:
        rows = [row for row in rows if transaction_matches_period(row, period)]
    if not rows:
        raise HTTPException(404, "No transactions found to fix")
    profile = db.get(GSTProfile, profile_id) if profile_id else db.get(GSTProfile, rows[0].profile_id)
    if not profile:
        raise HTTPException(404, "GST profile not found for fixes")
    logs = fix_detected_issues(rows, profile, user.id, db)
    for log in logs:
        db.add(log)
    db.commit()
    remaining = len(build_audit_summary(rows, profile)["details"])
    return AuditFixResponse(
        fixed_count=len(logs),
        logs=logs,
        remaining_issues=remaining,
    )


@router.get("/auditor/logs", response_model=list[IssueLogOut])
def auditor_logs(
    profile_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = select(IssueLog).where(IssueLog.user_id == user.id)
    if profile_id:
        stmt = stmt.where(IssueLog.profile_id == profile_id)
    logs = db.scalars(stmt.order_by(IssueLog.created_at.desc())).all()
    return logs


@router.post("/marketplaces/detect", response_model=MarketplaceDetectResponse)
def detect_marketplace_route(
    payload: MarketplaceDetectIn,
):
    marketplace, confidence = detect_marketplace(payload.file_contents)
    reason = "Detected marketplace by known file patterns"
    return MarketplaceDetectResponse(
        marketplace=marketplace,
        confidence=confidence,
        reason=reason,
    )


@router.put("/transactions/{transaction_id}", response_model=TransactionOut)
def update_transaction(
    transaction_id: int,
    payload: TransactionUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_paid_access(user, db)
    txn = db.get(NormalizedTransaction, transaction_id)
    if not txn or txn.user_id != user.id:
        raise HTTPException(404, "Transaction not found")
    apply_transaction_update(txn, payload.model_dump(exclude_unset=True))
    db.commit()
    db.refresh(txn)
    return txn


@router.delete("/transactions/{transaction_id}")
def delete_transaction(
    transaction_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_paid_access(user, db)
    txn = db.get(NormalizedTransaction, transaction_id)
    if not txn or txn.user_id != user.id:
        raise HTTPException(404, "Transaction not found")
    db.delete(txn)
    db.commit()
    return {"ok": True}


def transaction_to_dict(row: NormalizedTransaction) -> dict:
    return TransactionOut.model_validate(row).model_dump(mode="json")


def apply_transaction_update(row: NormalizedTransaction, values: dict) -> None:
    for key, value in values.items():
        setattr(row, key, value)

    recalculated = finalize_transaction(transaction_to_dict(row))
    for key in (
        "qty",
        "taxable_value",
        "gst_rate",
        "igst",
        "cgst",
        "sgst",
        "cess",
        "tcs",
        "tds",
        "gross_amount",
        "discount_seller",
        "discount_platform",
        "settlement_amount",
        "invoice_date",
        "document_date",
        "doc_type",
        "buyer_state_code",
        "buyer_state_name",
        "hsn",
        "validation_status",
        "validation_errors",
    ):
        if key in recalculated:
            setattr(row, key, recalculated[key])


def transaction_matches_period(row: NormalizedTransaction, period: str) -> bool:
    return row_belongs_to_period(transaction_to_dict(row), period)


def transaction_dicts(
    user_id: int, profile_id: int, period: str, db: Session, valid_only: bool = True
) -> list[dict]:
    stmt = select(NormalizedTransaction).where(
        NormalizedTransaction.user_id == user_id,
        NormalizedTransaction.profile_id == profile_id,
    )
    if valid_only:
        stmt = stmt.where(NormalizedTransaction.validation_status == "valid")
    rows = usable_transaction_rows(db.scalars(stmt).all(), db)
    return [
        transaction_to_dict(row)
        for row in rows
        if transaction_matches_period(row, period)
    ]


def validation_error_count(
    user_id: int, profile_id: int, period: str, db: Session
) -> int:
    rows = db.scalars(
        select(NormalizedTransaction).where(
            NormalizedTransaction.user_id == user_id,
            NormalizedTransaction.profile_id == profile_id,
            NormalizedTransaction.validation_status.in_(["error", "invalid"]),
        )
    ).all()
    rows = usable_transaction_rows(rows, db)
    return sum(1 for row in rows if transaction_matches_period(row, period))


def load_reference_gstr1(gstin: str, period: str) -> dict | None:
    candidates = [
        Path(f"/home/jarvis/Downloads/GSTR1_returns_{gstin}_monthly_{period}.json"),
        Path(f"/home/jarvis/Downloads/gstr1-{period}.json"),
        Path(f"exports/gst_bharat_gstr1_{gstin}_{period}.json"),
    ]
    for path in candidates:
        if not path.exists():
            continue
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
    return None


@router.post("/gstr1/generate")
def generate_gstr1(
    payload: GenerateGSTR1In,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_paid_access(user, db, "online_seller")
    profile = db.get(GSTProfile, payload.profile_id)
    if not profile or profile.user_id != user.id:
        raise HTTPException(404, "Profile not found")
    require_valid_period(payload.period)
    blockers = validation_error_count(user.id, profile.id, payload.period, db)
    if blockers:
        raise HTTPException(
            422,
            f"Resolve {blockers} validation error rows before generating GSTR-1 JSON",
        )
    export_mode = normalize_export_mode(payload.export_mode)
    rows = transaction_dicts(
        user.id,
        profile.id,
        payload.period,
        db,
        valid_only=export_mode == CLEAN_PORTAL,
    )
    gstr = build_gstr1_json(profile.gstin, payload.period, rows, export_mode)
    final_validation = validate_gstr1_export(gstr, export_mode)

    if export_mode == CLEAN_PORTAL and not final_validation["valid"]:
        raise HTTPException(
            422,
            {
                "message": "Final GSTR-1 validation failed",
                "errors": final_validation["errors"],
                "warnings": final_validation["warnings"],
            },
        )
    generation_report = gstr1_generation_report(gstr, rows, export_mode)
    if export_mode == CLEAN_PORTAL and generation_report["errors"]:
        raise HTTPException(
            422,
            {
                "message": "GSTR-1 document issue validation failed",
                "errors": generation_report["errors"],
            },
        )
    export_rows = [row for row in rows if row.get("validation_status") == "valid"]
    settings = get_settings()
    base = settings.export_dir / str(user.id) / profile.gstin / payload.period
    base.mkdir(parents=True, exist_ok=True)
    json_path = base / "gstr1.json"
    json_path.write_text(json.dumps(gstr, indent=2), encoding="utf-8")
    excel_path = write_gstr1_excel(base / "gstr1.xlsx", gstr, export_rows)
    export = GSTR1JsonExport(
        user_id=user.id,
        profile_id=profile.id,
        period=payload.period,
        json_path=str(json_path),
        excel_path=str(excel_path),
    )
    db.add(export)
    uploaded_files_deleted = clear_uploaded_files_for_profile_period(
        user.id,
        profile.id,
        payload.period,
        db,
    )
    db.add(
        AuditLog(
            user_id=user.id,
            action="gstr1.generate",
            entity_type="gstr1_json_exports",
            metadata_json=json.dumps({"uploaded_files_deleted": uploaded_files_deleted}),
        )
    )
    db.commit()
    db.refresh(export)
    return {
        "status": "generated",
        "json": gstr,
        "export_mode": export_mode,
        "report": generation_report,
        "parity_report": (
            compare_against_reference(reference, gstr)
            if export_mode == GSTTOOL_COMPATIBLE
            and (reference := load_reference_gstr1(profile.gstin, payload.period))
            else None
        ),
        "download_json": f"/gstr1/export/{export.id}",
        "download_excel": f"/gstr1/export/{export.id}?format=xlsx",
    }


@router.get("/gstr1/history")
def gstr1_history(
    profile_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = (
        select(GSTR1JsonExport)
        .where(GSTR1JsonExport.user_id == user.id)
        .order_by(GSTR1JsonExport.id.desc())
    )
    if profile_id:
        stmt = stmt.where(GSTR1JsonExport.profile_id == profile_id)
    exports = db.scalars(stmt.limit(50)).all()
    return [
        {
            "id": export.id,
            "profile_id": export.profile_id,
            "period": export.period,
            "status": export.status,
            "created_at": export.created_at,
            "download_json": f"/gstr1/export/{export.id}",
            "download_excel": f"/gstr1/export/{export.id}?format=xlsx",
        }
        for export in exports
    ]


@router.get("/gstr1/export/{export_id}")
def gstr1_export_download(
    export_id: int,
    format: str = "json",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_paid_access(user, db, "online_seller")
    export = db.get(GSTR1JsonExport, export_id)
    if not export or export.user_id != user.id:
        raise HTTPException(404, "Export not found")
    if format == "xlsx":
        if not export.excel_path:
            raise HTTPException(404, "GSTR-1 Excel not found")
        uploaded_files_deleted = clear_uploaded_files_for_profile_period(
            user.id,
            export.profile_id,
            export.period,
            db,
        )
        export.status = "downloaded"
        if uploaded_files_deleted:
            db.add(
                AuditLog(
                    user_id=user.id,
                    action="gstr1.download.cleanup_uploads",
                    entity_type="gstr1_json_exports",
                    entity_id=str(export.id),
                    metadata_json=json.dumps({"uploaded_files_deleted": uploaded_files_deleted}),
                )
            )
        db.commit()
        return FileResponse(export.excel_path, filename=Path(export.excel_path).name)
    if not export.json_path:
        raise HTTPException(404, "GSTR-1 JSON not found")
    uploaded_files_deleted = clear_uploaded_files_for_profile_period(
        user.id,
        export.profile_id,
        export.period,
        db,
    )
    export.status = "downloaded"
    if uploaded_files_deleted:
        db.add(
            AuditLog(
                user_id=user.id,
                action="gstr1.download.cleanup_uploads",
                entity_type="gstr1_json_exports",
                entity_id=str(export.id),
                metadata_json=json.dumps({"uploaded_files_deleted": uploaded_files_deleted}),
            )
        )
    db.commit()
    return FileResponse(export.json_path, filename=Path(export.json_path).name)


@router.get("/gstr1/preview/{period}")
def preview_gstr1(
    period: str,
    profile_id: int,
    export_mode: str = GSTTOOL_COMPATIBLE,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_paid_access(user, db, "online_seller")
    profile = db.get(GSTProfile, profile_id)

    if not profile or profile.user_id != user.id:
        raise HTTPException(404, "Profile not found")
    require_valid_period(period)

    mode = normalize_export_mode(export_mode)
    rows = transaction_dicts(
        user.id,
        profile.id,
        period,
        db,
        valid_only=mode == CLEAN_PORTAL,
    )

    blockers = validation_error_count(
        user.id,
        profile.id,
        period,
        db,
    )

    preview = build_gstr1_json(
        profile.gstin,
        period,
        rows,
        mode,
    )
    reference = load_reference_gstr1(profile.gstin, period)

    return {
        "can_generate": blockers == 0,
        "validation_blockers": blockers,
        "export_mode": mode,
        "parity_report": (
            compare_against_reference(reference, preview)
            if mode == GSTTOOL_COMPATIBLE and reference
            else None
        ),
        "preview": preview,
    }


@router.get("/gstr1/download-json/{period}")
def download_json(
    period: str,
    profile_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_paid_access(user, db, "online_seller")
    export = db.scalar(
        select(GSTR1JsonExport)
        .where(
            GSTR1JsonExport.user_id == user.id,
            GSTR1JsonExport.profile_id == profile_id,
            GSTR1JsonExport.period == period,
        )
        .order_by(GSTR1JsonExport.id.desc())
    )
    if not export or not export.json_path:
        raise HTTPException(404, "Export not found")
    clear_uploaded_files_for_profile_period(
        user.id,
        profile_id,
        period,
        db,
    )
    export.status = "downloaded"
    db.commit()
    return FileResponse(export.json_path, filename=f"gstr1-{period}.json")


@router.get("/gstr1/download-excel/{period}")
def download_excel(
    period: str,
    profile_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_paid_access(user, db, "online_seller")
    export = db.scalar(
        select(GSTR1JsonExport)
        .where(
            GSTR1JsonExport.user_id == user.id,
            GSTR1JsonExport.profile_id == profile_id,
            GSTR1JsonExport.period == period,
        )
        .order_by(GSTR1JsonExport.id.desc())
    )
    if not export or not export.excel_path:
        raise HTTPException(404, "Export not found")
    clear_uploaded_files_for_profile_period(
        user.id,
        profile_id,
        period,
        db,
    )
    export.status = "downloaded"
    db.commit()
    return FileResponse(export.excel_path, filename=f"gstr1-{period}.xlsx")


@router.post("/tally/company")
def tally_company(
    payload: TallyCompanyIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_paid_access(user, db, "ecom_tally")
    profile = db.get(GSTProfile, payload.profile_id)
    if not profile or profile.user_id != user.id:
        raise HTTPException(404, "Profile not found")
    company = TallyCompany(
        user_id=user.id,
        profile_id=profile.id,
        company_name=payload.company_name,
        gstin=(payload.gstin or profile.gstin).upper(),
        financial_year=payload.financial_year or profile.financial_year,
        state=payload.state,
        auto_create_ledger=1 if payload.auto_create_ledger else 0,
        tally_guid=payload.tally_guid,
    )
    db.add(company)
    db.add(
        AuditLog(
            user_id=user.id, action="tally.company.create", entity_type="tally_company"
        )
    )
    db.commit()
    db.refresh(company)
    return {
        "id": company.id,
        "company_name": company.company_name,
        "gstin": company.gstin,
        "financial_year": company.financial_year,
        "state": company.state,
        "auto_create_ledger": bool(company.auto_create_ledger),
    }


@router.get("/tally/companies")
def tally_companies(
    profile_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_paid_access(user, db, "ecom_tally")
    stmt = (
        select(TallyCompany)
        .where(TallyCompany.user_id == user.id)
        .order_by(TallyCompany.id.desc())
    )
    if profile_id:
        stmt = stmt.where(TallyCompany.profile_id == profile_id)
    companies = db.scalars(stmt.limit(50)).all()
    return [
        {
            "id": company.id,
            "company_name": company.company_name,
            "gstin": company.gstin,
            "financial_year": company.financial_year,
            "state": company.state,
            "auto_create_ledger": bool(company.auto_create_ledger),
            "tally_guid": company.tally_guid,
        }
        for company in companies
    ]


@router.post("/tally/import", response_model=BatchStatus)
async def tally_import(
    platform: str,
    background_tasks: BackgroundTasks,
    profile_id: int,
    files: list[UploadFile] = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return await upload_import(
        platform=platform,
        background_tasks=background_tasks,
        profile_id=profile_id,
        files=files,
        required_plan="ecom_tally",
        user=user,
        db=db,
    )


@router.get("/tally/mapping/{company_id}")
def tally_mapping(
    company_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_paid_access(user, db, "ecom_tally")
    company = db.get(TallyCompany, company_id)
    if not company or company.user_id != user.id:
        raise HTTPException(404, "Company not found")
    mapping = db.scalar(
        select(TallyLedgerMapping)
        .where(TallyLedgerMapping.company_id == company.id)
        .order_by(TallyLedgerMapping.id.desc())
    )
    return {
        "company_id": company.id,
        "mapping": json.loads(mapping.mapping_json) if mapping else {},
    }


@router.post("/tally/mapping/{company_id}")
def save_tally_mapping(
    company_id: int,
    payload: dict[str, str],
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_paid_access(user, db, "ecom_tally")
    company = db.get(TallyCompany, company_id)
    if not company or company.user_id != user.id:
        raise HTTPException(404, "Company not found")
    mapping = TallyLedgerMapping(
        company_id=company.id, mapping_json=json.dumps(payload)
    )
    db.add(mapping)
    db.add(
        AuditLog(
            user_id=user.id,
            action="tally.mapping.save",
            entity_type="tally_ledger_mapping",
            entity_id=str(company.id),
        )
    )
    db.commit()
    return {"company_id": company.id, "mapping": payload, "status": "saved"}


@router.post("/tally/generate-xml")
@router.post("/tally/generate")
def tally_xml(
    payload: TallyGenerateIn,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_paid_access(user, db, "ecom_tally")
    company = db.get(TallyCompany, payload.company_id)
    if not company or company.user_id != user.id:
        raise HTTPException(404, "Company not found")
    if company.profile_id != payload.profile_id:
        raise HTTPException(422, "Selected company does not belong to this GST profile")
    rows = transaction_dicts(
        user.id, payload.profile_id, payload.period, db, valid_only=True
    )
    if not rows:
        raise HTTPException(422, "No valid transactions found for this GST profile and period")
    vouchers = build_vouchers(rows, payload.ledger_mapping)
    if not vouchers:
        raise HTTPException(422, "No Tally vouchers could be built from the selected transactions")
    xml = build_tally_xml(
        company.company_name, rows, payload.ledger_mapping, payload.auto_create_ledgers
    )
    validation = validate_tally_xml(xml, vouchers)
    settings = get_settings()
    base = settings.export_dir / str(user.id) / "tally" / payload.period
    base.mkdir(parents=True, exist_ok=True)
    xml_path = base / f"tally-{payload.period}-{uuid4().hex}.xml"
    xml_path.write_text(xml, encoding="utf-8")
    excel_path = write_voucher_excel(
        base / f"tally-vouchers-{payload.period}-{uuid4().hex}.xlsx", vouchers
    )
    export = TallyExport(
        user_id=user.id,
        profile_id=payload.profile_id,
        company_id=company.id,
        period=payload.period,
        xml_path=str(xml_path),
        voucher_excel_path=str(excel_path),
        voucher_count=len(vouchers),
        validation_json=json.dumps(validation),
    )
    db.add(export)
    db.flush()
    for voucher in vouchers:
        db.add(
            TallyVoucher(
                user_id=user.id,
                profile_id=payload.profile_id,
                company_id=company.id,
                transaction_id=voucher.get("source", {}).get("id"),
                voucher_no=str(voucher["voucher_no"]),
                voucher_type=str(voucher["voucher_type"]),
                voucher_date=voucher.get("date"),
                party_ledger=str(voucher["party_ledger"]),
                taxable_value=money(voucher.get("taxable_value")),
                total_tax=money(voucher.get("total_tax")),
                amount=money(voucher.get("amount")),
                status="ready" if validation["valid"] else "error",
                raw_json=json.dumps(voucher, default=str),
            )
        )
    db.add(
        AuditLog(
            user_id=user.id,
            action="tally.export.generate",
            entity_type="tally_export",
            entity_id=str(export.id),
        )
    )
    db.commit()
    return {
        "id": export.id,
        "voucher_count": len(vouchers),
        "validation": validation,
        "download": f"/tally/export/{export.id}",
        "download_excel": f"/tally/export/{export.id}?format=xlsx",
    }


@router.get("/tally/history")
def tally_history(
    profile_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_paid_access(user, db, "ecom_tally")
    stmt = (
        select(TallyExport)
        .where(TallyExport.user_id == user.id)
        .order_by(TallyExport.id.desc())
    )
    if profile_id:
        stmt = stmt.where(TallyExport.profile_id == profile_id)
    exports = db.scalars(stmt.limit(50)).all()
    return [
        {
            "id": row.id,
            "profile_id": row.profile_id,
            "company_id": row.company_id,
            "period": row.period,
            "voucher_count": row.voucher_count,
            "status": row.status,
            "validation": json.loads(row.validation_json or "{}"),
            "created_at": row.created_at,
        }
        for row in exports
    ]


@router.get("/tally/export/{export_id}")
def tally_export_download(
    export_id: int,
    format: str = "xml",
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    require_paid_access(user, db, "ecom_tally")
    export = db.get(TallyExport, export_id)
    if not export or export.user_id != user.id:
        raise HTTPException(404, "Export not found")
    if format == "xlsx":
        if not export.voucher_excel_path:
            raise HTTPException(404, "Voucher Excel not found")
        export.status = "downloaded"
        db.commit()
        return FileResponse(
            export.voucher_excel_path, filename=Path(export.voucher_excel_path).name
        )
    if not export.xml_path:
        raise HTTPException(404, "XML not found")
    export.status = "downloaded"
    db.commit()
    return FileResponse(export.xml_path, filename=Path(export.xml_path).name)


@router.get("/tally/download-xml/{export_id}")
def tally_download(
    export_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    # Legacy path-based download. Keep protected even though modern downloads use export IDs.
    require_paid_access(user, db, "ecom_tally")
    path = get_settings().export_dir / str(user.id) / export_id
    if not path.exists():
        raise HTTPException(404, "Export not found")
    return FileResponse(path, filename=export_id)


def save_upload(upload: UploadFile, base: Path) -> Path:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS and suffix != ".json":
        raise HTTPException(422, f"Unsupported file type: {upload.filename}")
    path = base / f"{uuid4().hex}{suffix}"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        shutil.copyfileobj(upload.file, handle)
    return path


@router.post("/reconcile/upload")
async def reconcile_upload(
    profile_id: int,
    portal_file: UploadFile = File(...),
    books_file: UploadFile = File(...),
    tax_tolerance: Decimal = Decimal("1.00"),
    date_tolerance_days: int = 3,
    enable_date_tolerance: bool = True,
    enable_fuzzy_invoice: bool = True,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.get(GSTProfile, profile_id)
    if not profile or profile.user_id != user.id:
        raise HTTPException(404, "Profile not found")
    if tax_tolerance < 0:
        raise HTTPException(422, "Tax tolerance cannot be negative")
    if date_tolerance_days < 0 or date_tolerance_days > 365:
        raise HTTPException(422, "Date tolerance must be between 0 and 365 days")
    batch = ReconciliationBatch(
        user_id=user.id, profile_id=profile.id, status="processing"
    )
    db.add(batch)
    db.flush()
    base = get_settings().upload_dir / str(user.id) / "reconcile" / str(batch.id)
    portal_path = save_upload(portal_file, base / "portal")
    books_path = save_upload(books_file, base / "books")
    portal_rows, portal_errors = normalize_rows(portal_path, "portal")
    book_rows, book_errors = normalize_rows(books_path, "books")
    settings = ReconSettings(
        tax_tolerance=money(tax_tolerance),
        date_tolerance_days=date_tolerance_days,
        enable_date_tolerance=enable_date_tolerance,
        enable_fuzzy_invoice=enable_fuzzy_invoice,
    )
    result_rows, summary = reconcile(book_rows, portal_rows, settings)
    report_path = (
        get_settings().export_dir
        / str(user.id)
        / "reconcile"
        / f"reconcile-{batch.id}.xlsx"
    )
    write_reconciliation_excel(
        report_path,
        result_rows,
        {**summary, "parser_errors": json.dumps(portal_errors + book_errors)},
    )
    for row in result_rows:
        db.add(ReconciliationRow(batch_id=batch.id, **row))
    batch.status = (
        "completed_with_errors" if portal_errors or book_errors else "completed"
    )
    batch.portal_rows = len(portal_rows)
    batch.book_rows = len(book_rows)
    batch.matched_rows = int(summary.get("matched", 0))
    batch.mismatch_rows = int(summary.get("total_rows", 0)) - batch.matched_rows
    batch.tax_difference = money(summary.get("tax_difference"))
    batch.itc_risk_amount = money(summary.get("itc_risk_amount"))
    batch.summary_json = json.dumps(
        {**summary, "parser_errors": portal_errors + book_errors}, default=str
    )
    batch.report_path = str(report_path)
    db.add(
        ReconciliationReport(
            batch_id=batch.id, report_type="full", path=str(report_path)
        )
    )
    db.add(
        AuditLog(
            user_id=user.id,
            action="reconcile.upload",
            entity_type="reconciliation_batch",
            entity_id=str(batch.id),
        )
    )
    db.commit()
    db.refresh(batch)
    return {
        "id": batch.id,
        "status": batch.status,
        "summary": json.loads(batch.summary_json or "{}"),
    }


@router.get("/reconcile/results/{batch_id}")
def reconcile_results(
    batch_id: int,
    category: str | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    batch = db.get(ReconciliationBatch, batch_id)
    if not batch or batch.user_id != user.id:
        raise HTTPException(404, "Batch not found")
    stmt = (
        select(ReconciliationRow)
        .where(ReconciliationRow.batch_id == batch.id)
        .order_by(ReconciliationRow.id.asc())
    )
    if category:
        stmt = stmt.where(ReconciliationRow.category == category)
    rows = db.scalars(stmt.limit(1000)).all()
    return {
        "id": batch.id,
        "status": batch.status,
        "summary": json.loads(batch.summary_json or "{}"),
        "categories": [
            "matched",
            "partially_matched",
            "invoice_mismatch",
            "tax_mismatch",
            "gstin_mismatch",
            "missing_in_books",
            "missing_in_portal",
            "duplicate_invoice",
            "invalid_gstin",
        ],
        "rows": [
            {
                "id": row.id,
                "supplier_gstin": row.supplier_gstin,
                "invoice_no": row.invoice_no,
                "invoice_date": row.invoice_date,
                "taxable_value": row.taxable_value,
                "igst": row.igst,
                "cgst": row.cgst,
                "sgst": row.sgst,
                "total_tax": row.total_tax,
                "tax_difference": row.tax_difference,
                "match_score": row.match_score,
                "category": row.category,
                "mismatch_reason": row.mismatch_reason,
            }
            for row in rows
        ],
    }


@router.get("/reconcile/report/{batch_id}")
def reconcile_report(
    batch_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    return reconcile_results(batch_id, None, user, db)


@router.get("/reconcile/history")
def reconcile_history(
    profile_id: int | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    stmt = (
        select(ReconciliationBatch)
        .where(ReconciliationBatch.user_id == user.id)
        .order_by(ReconciliationBatch.id.desc())
    )
    if profile_id:
        stmt = stmt.where(ReconciliationBatch.profile_id == profile_id)
    batches = db.scalars(stmt.limit(50)).all()
    return [
        {
            "id": batch.id,
            "profile_id": batch.profile_id,
            "status": batch.status,
            "portal_rows": batch.portal_rows,
            "book_rows": batch.book_rows,
            "matched_rows": batch.matched_rows,
            "mismatch_rows": batch.mismatch_rows,
            "tax_difference": batch.tax_difference,
            "itc_risk_amount": batch.itc_risk_amount,
            "summary": json.loads(batch.summary_json or "{}"),
            "created_at": batch.created_at,
        }
        for batch in batches
    ]


@router.get("/reconcile/download/{batch_id}")
def reconcile_download(
    batch_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    batch = db.get(ReconciliationBatch, batch_id)
    if not batch or batch.user_id != user.id:
        raise HTTPException(404, "Batch not found")
    if not batch.report_path:
        raise HTTPException(404, "Report not found")
    return FileResponse(batch.report_path, filename=f"reconciliation-{batch.id}.xlsx")
