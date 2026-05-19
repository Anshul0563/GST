from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
import json
import shutil
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

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
)
from app.parsers.factory import get_parser
from app.schemas.dto import (
    BatchStatus,
    CreatePaymentOrderIn,
    DashboardSummary,
    GSTProfileIn,
    GSTProfileOut,
    GenerateGSTR1In,
    LoginIn,
    RegisterIn,
    ReconcileSettingsIn,
    TallyCompanyIn,
    TallyGenerateIn,
    Token,
    TransactionOut,
    TransactionUpdate,
    VerifyPaymentIn,
)
from app.services.billing import create_razorpay_order, plan_amount_paise, public_plans, verify_razorpay_signature
from app.services.excel_export import write_gstr1_excel
from app.services.gst import build_gstr1_json
from app.services.reconciliation import ReconSettings, normalize_rows, reconcile, write_reconciliation_excel
from app.services.tally import build_tally_xml, build_vouchers, validate_tally_xml, write_voucher_excel
from app.services.transaction_normalizer import finalize_transaction
from app.services.validation import money, validate_gstin
from app.utils.security import create_access_token, hash_password, verify_password


router = APIRouter()
ALLOWED_EXTENSIONS = {".xlsx", ".xlsm", ".xls", ".csv"}
STALE_IMPORT_AFTER = timedelta(minutes=5)


def settle_stale_import(batch: PlatformImportBatch, db: Session) -> None:
    if batch.status not in {"queued", "processing"}:
        return
    if not batch.created_at or datetime.utcnow() - batch.created_at <= STALE_IMPORT_AFTER:
        return
    batch.status = "failed"
    batch.error_report_json = json.dumps([{"error": "Import worker did not complete. Please retry upload."}])
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
        return (errors if isinstance(errors, list) else []), (debug if isinstance(debug, dict) else {})
    return (raw if isinstance(raw, list) else []), {}


@router.post("/auth/register", response_model=Token)
def register(payload: RegisterIn, db: Session = Depends(get_db)):
    existing = db.scalar(select(User).where(User.email == payload.email.lower()))
    if existing:
        raise HTTPException(409, "Email is already registered")
    user = User(email=payload.email.lower(), password_hash=hash_password(payload.password), full_name=payload.full_name)
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
def me(user: User = Depends(get_current_user)):
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": getattr(user, "role", "user"),
        "plan": getattr(user, "plan", "free"),
        "subscription_status": getattr(user, "subscription_status", "inactive"),
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
def billing_status(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    latest = db.scalar(select(PaymentOrder).where(PaymentOrder.user_id == user.id).order_by(PaymentOrder.id.desc()))
    return {
        "role": getattr(user, "role", "user"),
        "plan": getattr(user, "plan", "free"),
        "subscription_status": getattr(user, "subscription_status", "inactive"),
        "free_access": getattr(user, "plan", "") == "admin_free",
        "free_access_reason": getattr(user, "free_access_reason", None),
        "latest_order": {
            "id": latest.id,
            "plan_id": latest.plan_id,
            "billing_cycle": latest.billing_cycle,
            "amount": latest.amount_paise / 100,
            "status": latest.status,
            "provider_order_id": latest.provider_order_id,
        } if latest else None,
    }


@router.post("/billing/create-order")
def create_payment_order(payload: CreatePaymentOrderIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
    order = PaymentOrder(user_id=user.id, plan_id=payload.plan_id, billing_cycle=payload.billing_cycle, amount_paise=amount_paise, currency="INR")
    db.add(order)
    db.flush()
    settings = get_settings()
    try:
        gateway_order = create_razorpay_order(settings, amount_paise, f"gstbharat_{order.id}")
    except RuntimeError as exc:
        raise HTTPException(502, str(exc)) from exc
    order.provider_order_id = str(gateway_order.get("id"))
    order.raw_response_json = json.dumps(gateway_order)
    db.add(AuditLog(user_id=user.id, action="billing.order.create", entity_type="payment_order", entity_id=str(order.id), metadata_json=json.dumps({"plan_id": payload.plan_id, "billing_cycle": payload.billing_cycle})))
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
        "gateway_configured": bool(settings.razorpay_key_id and settings.razorpay_key_secret),
    }


@router.post("/billing/verify")
def verify_payment(payload: VerifyPaymentIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    order = db.get(PaymentOrder, payload.order_id)
    if not order or order.user_id != user.id:
        raise HTTPException(404, "Payment order not found")
    if order.provider_order_id != payload.razorpay_order_id:
        raise HTTPException(422, "Razorpay order ID mismatch")
    settings = get_settings()
    if not verify_razorpay_signature(settings, payload.razorpay_order_id, payload.razorpay_payment_id, payload.razorpay_signature):
        raise HTTPException(422, "Invalid payment signature")
    order.status = "paid"
    order.provider_payment_id = payload.razorpay_payment_id
    order.paid_at = datetime.utcnow()
    user.plan = order.plan_id
    user.subscription_status = "active"
    db.add(AuditLog(user_id=user.id, action="billing.payment.verified", entity_type="payment_order", entity_id=str(order.id)))
    db.commit()
    return {"status": "paid", "plan": user.plan, "subscription_status": user.subscription_status}


@router.post("/gst-profile", response_model=GSTProfileOut)
def create_profile(payload: GSTProfileIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    gstin = payload.gstin.upper()
    if not validate_gstin(gstin):
        raise HTTPException(422, "Invalid GSTIN")
    profile = GSTProfile(
        user_id=user.id,
        gstin=gstin,
        legal_name=payload.legal_name,
        trade_name=payload.trade_name,
        state_code=gstin[:2],
        filing_frequency=payload.filing_frequency,
        financial_year=payload.financial_year,
        return_period=payload.return_period,
    )
    db.add(profile)
    db.add(AuditLog(user_id=user.id, action="gst_profile.create", entity_type="gst_profile"))
    db.commit()
    db.refresh(profile)
    return profile


@router.get("/gst-profile", response_model=list[GSTProfileOut])
def list_profiles(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return db.scalars(select(GSTProfile).where(GSTProfile.user_id == user.id)).all()


@router.post("/demo/seed")
def seed_demo(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.scalar(select(GSTProfile).where(GSTProfile.user_id == user.id).order_by(GSTProfile.id.asc()))
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
    existing = db.scalars(select(NormalizedTransaction).where(NormalizedTransaction.user_id == user.id, NormalizedTransaction.profile_id == profile.id)).all()
    if existing:
        return {"profile_id": profile.id, "transactions": len(existing), "status": "already_seeded"}
    batch = PlatformImportBatch(user_id=user.id, profile_id=profile.id, platform="demo", status="completed", parsed_rows=6, error_rows=0, completed_at=datetime.utcnow())
    db.add(batch)
    db.flush()
    rows = [
        {"platform": "meesho", "etin": "07AARCM9332R1CQ", "order_id": "MSH-1001", "order_item_id": "1", "invoice_no": "MSH-28491", "invoice_date": "2026-04-04", "buyer_state_code": "37", "buyer_state_name": "Andhra Pradesh", "hsn": "711790", "product_name": "Fashion jewellery set", "sku": "JWL-01", "qty": 1, "taxable_value": 1327.42, "gst_rate": 3, "igst": 39.82, "tcs": 13.27, "source_file": "tcs_sales.xlsx"},
        {"platform": "amazon", "etin": "29AAICA3918J1C9", "order_id": "405-1122", "order_item_id": "A1", "invoice_no": "IN-7781", "invoice_date": "2026-04-08", "buyer_state_code": "07", "buyer_state_name": "Delhi", "hsn": "7117", "product_name": "Oxidised necklace", "sku": "AMZ-JW-2", "qty": 2, "taxable_value": 2600, "gst_rate": 3, "cgst": 39, "sgst": 39, "tcs": 26, "source_file": "MTR_B2C.csv"},
        {"platform": "flipkart", "etin": "29AACCF0683K1C8", "order_id": "OD3301", "order_item_id": "FK1", "invoice_no": "FK-9982", "invoice_date": "2026-04-12", "buyer_state_code": "29", "buyer_state_name": "Karnataka", "hsn": "4202", "product_name": "Travel pouch", "sku": "FK-BAG-1", "qty": 1, "taxable_value": 4100, "gst_rate": 18, "igst": 738, "tcs": 41, "source_file": "sales-report.xlsx:hidden"},
        {"platform": "meesho", "etin": "07AARCM9332R1CQ", "order_id": "MSH-1001", "order_item_id": "1-R", "invoice_no": "CN-120", "invoice_date": "2026-04-16", "doc_type": "credit_note", "buyer_state_code": "37", "buyer_state_name": "Andhra Pradesh", "hsn": "711790", "product_name": "Fashion jewellery set", "sku": "JWL-01", "qty": 1, "taxable_value": 420, "gst_rate": 3, "igst": 12.6, "tcs": 4.2, "source_file": "tcs_sales_return.xlsx"},
        {"platform": "jiomart", "etin": "27AABCI6363G1C7", "order_id": "JM-901", "order_item_id": "J1", "invoice_no": "JM-551", "invoice_date": "2026-04-18", "buyer_state_code": "24", "buyer_state_name": "Gujarat", "hsn": "3926", "product_name": "Home organizer", "sku": "ORG-9", "qty": 4, "taxable_value": 1199.2, "gst_rate": 18, "igst": 215.86, "source_file": "jiomart-sales.xlsx"},
        {"platform": "custom", "etin": "29AACCF0683K1C8", "order_id": "CUS-18", "order_item_id": "C1", "invoice_no": "CUST-18", "invoice_date": "2026-04-21", "buyer_state_code": "07", "buyer_state_name": "Delhi", "hsn": "4819", "product_name": "Packaging material", "sku": "PACK-1", "qty": 10, "taxable_value": 850, "gst_rate": 12, "cgst": 51, "sgst": 51, "source_file": "custom.xlsx"},
    ]
    for row in rows:
        row = dict(row)
        txn = finalize_transaction({
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
        })
        db.add(NormalizedTransaction(user_id=user.id, profile_id=profile.id, batch_id=batch.id, **txn))
    db.add(AuditLog(user_id=user.id, action="demo.seed", entity_type="gst_profile", entity_id=str(profile.id)))
    db.commit()
    return {"profile_id": profile.id, "transactions": len(rows), "status": "seeded"}


@router.put("/gst-profile/{profile_id}", response_model=GSTProfileOut)
def update_profile(profile_id: int, payload: GSTProfileIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.get(GSTProfile, profile_id)
    if not profile or profile.user_id != user.id:
        raise HTTPException(404, "Profile not found")
    gstin = payload.gstin.upper()
    if not validate_gstin(gstin):
        raise HTTPException(422, "Invalid GSTIN")
    for key, value in payload.model_dump().items():
        setattr(profile, key, value)
    profile.gstin = gstin
    profile.state_code = gstin[:2]
    db.commit()
    db.refresh(profile)
    return profile


@router.post("/imports/{platform}/upload", response_model=BatchStatus)
async def upload_import(
    platform: str,
    background_tasks: BackgroundTasks,
    profile_id: int,
    files: list[UploadFile] = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    profile = db.get(GSTProfile, profile_id)
    if not profile or profile.user_id != user.id:
        raise HTTPException(404, "Profile not found")
    settings = get_settings()
    batch = PlatformImportBatch(user_id=user.id, profile_id=profile.id, platform=platform.lower(), status="queued")
    db.add(batch)
    db.flush()
    stored_paths: list[Path] = []
    for upload in files:
        suffix = Path(upload.filename or "").suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(422, f"Unsupported file type: {upload.filename}")
        stored = settings.upload_dir / str(user.id) / str(batch.id) / f"{uuid4().hex}{suffix}"
        stored.parent.mkdir(parents=True, exist_ok=True)
        with stored.open("wb") as handle:
            shutil.copyfileobj(upload.file, handle)
        stored_paths.append(stored)
        db.add(UploadedFile(batch_id=batch.id, user_id=user.id, original_name=upload.filename or stored.name, stored_path=str(stored), content_type=upload.content_type, size_bytes=stored.stat().st_size))
    db.add(AuditLog(user_id=user.id, action="import.upload", entity_type="platform_import_batch", entity_id=str(batch.id), metadata_json=json.dumps({"platform": platform})))
    db.commit()
    background_tasks.add_task(process_import_batch, batch.id, [str(path) for path in stored_paths])
    return BatchStatus(id=batch.id, platform=batch.platform, status=batch.status, parsed_rows=0, error_rows=0)


def process_import_batch(batch_id: int, file_paths: list[str]):
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        batch = db.get(PlatformImportBatch, batch_id)
        if not batch:
            return
        profile = db.get(GSTProfile, batch.profile_id)
        batch.status = "processing"
        db.commit()
        parser = get_parser(batch.platform)(profile.gstin, profile.return_period)
        result = parser.parse([Path(path) for path in file_paths])
        seen_keys: set[tuple[int, str | None, str | None, str | None]] = set()
        inserted_rows = 0
        validation_error_rows = 0
        for txn in result.transactions:
            key = (batch.profile_id, txn.get("platform"), txn.get("invoice_no"), txn.get("order_item_id"))
            duplicate = key in seen_keys or db.scalar(select(NormalizedTransaction).where(
                NormalizedTransaction.profile_id == key[0],
                NormalizedTransaction.platform == key[1],
                NormalizedTransaction.invoice_no == key[2],
                NormalizedTransaction.order_item_id == key[3],
            ))
            if duplicate:
                continue
            seen_keys.add(key)
            db.add(NormalizedTransaction(user_id=batch.user_id, profile_id=batch.profile_id, batch_id=batch.id, **txn))
            inserted_rows += 1
            validation_error_rows += 1 if txn.get("validation_status") == "error" else 0
        batch.parsed_rows = inserted_rows
        batch.error_rows = len(result.errors) + validation_error_rows
        batch.error_report_json = json.dumps({"parser_errors": result.errors, "debug": result.debug}, default=str)
        batch.status = "completed" if batch.error_rows == 0 else "completed_with_errors"
        batch.completed_at = datetime.utcnow()
        db.add(AuditLog(user_id=batch.user_id, action="import.processed", entity_type="platform_import_batch", entity_id=str(batch.id)))
        db.commit()
    except Exception as exc:
        db.rollback()
        batch = db.get(PlatformImportBatch, batch_id)
        if batch:
            batch.status = "failed"
            batch.error_report_json = json.dumps([{"error": str(exc)}])
            db.commit()
    finally:
        db.close()


@router.get("/imports/{batch_id}/status", response_model=BatchStatus)
def import_status(batch_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    batch = db.get(PlatformImportBatch, batch_id)
    if not batch or batch.user_id != user.id:
        raise HTTPException(404, "Batch not found")
    settle_stale_import(batch, db)
    parser_errors, debug = read_import_report(batch)
    return BatchStatus(id=batch.id, platform=batch.platform, status=batch.status, parsed_rows=batch.parsed_rows, error_rows=batch.error_rows, errors=parser_errors, debug=debug)


@router.get("/imports", response_model=list[BatchStatus])
def list_imports(profile_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(PlatformImportBatch).where(PlatformImportBatch.user_id == user.id).order_by(PlatformImportBatch.id.desc())
    if profile_id:
        stmt = stmt.where(PlatformImportBatch.profile_id == profile_id)
    batches = db.scalars(stmt.limit(50)).all()
    for batch in batches:
        settle_stale_import(batch, db)
    return [
        (lambda report: BatchStatus(
            id=batch.id,
            platform=batch.platform,
            status=batch.status,
            parsed_rows=batch.parsed_rows,
            error_rows=batch.error_rows,
            errors=report[0],
            debug=report[1],
        ))(read_import_report(batch))
        for batch in batches
    ]


@router.get("/imports/{batch_id}/errors")
def import_errors(batch_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    batch = db.get(PlatformImportBatch, batch_id)
    if not batch or batch.user_id != user.id:
        raise HTTPException(404, "Batch not found")
    parser_errors, debug = read_import_report(batch)
    rows = db.scalars(select(NormalizedTransaction).where(NormalizedTransaction.batch_id == batch_id, NormalizedTransaction.validation_status == "error")).all()
    return {"parser_errors": parser_errors, "parser_debug": debug, "row_errors": [TransactionOut.model_validate(row).model_dump(mode="json") for row in rows]}


@router.delete("/imports/{batch_id}")
def delete_import_batch(batch_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    batch = db.get(PlatformImportBatch, batch_id)
    if not batch or batch.user_id != user.id:
        raise HTTPException(404, "Batch not found")
    settle_stale_import(batch, db)
    if batch.status in {"queued", "processing"}:
        raise HTTPException(409, "Import is still processing")

    files = db.scalars(select(UploadedFile).where(UploadedFile.batch_id == batch.id, UploadedFile.user_id == user.id)).all()
    stored_paths = [uploaded.stored_path for uploaded in files if uploaded.stored_path]
    for txn in db.scalars(select(NormalizedTransaction).where(NormalizedTransaction.batch_id == batch.id, NormalizedTransaction.user_id == user.id)).all():
        db.delete(txn)
    for uploaded in files:
        db.delete(uploaded)
    db.add(AuditLog(user_id=user.id, action="import.delete", entity_type="platform_import_batch", entity_id=str(batch.id)))
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
def transactions(profile_id: int | None = None, period: str | None = None, platform: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(NormalizedTransaction).where(NormalizedTransaction.user_id == user.id)
    if profile_id:
        stmt = stmt.where(NormalizedTransaction.profile_id == profile_id)
    if period:
        stmt = stmt.where(NormalizedTransaction.filing_period == period)
    if platform:
        stmt = stmt.where(NormalizedTransaction.platform == platform)
    return db.scalars(stmt.limit(1000)).all()


@router.get("/dashboard/summary", response_model=DashboardSummary)
def dashboard_summary(profile_id: int | None = None, period: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(NormalizedTransaction).where(NormalizedTransaction.user_id == user.id)
    if profile_id:
        stmt = stmt.where(NormalizedTransaction.profile_id == profile_id)
    if period:
        stmt = stmt.where(NormalizedTransaction.filing_period == period)
    rows = db.scalars(stmt).all()
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
        pending_errors += 1 if row.validation_status == "error" else 0
        platform = row.platform or "unknown"
        state = row.buyer_state_code or "NA"
        platform_totals.setdefault(platform, {"platform": platform, "taxable_value": money(0), "gst": money(0), "rows": 0})
        state_totals.setdefault(state, {"state_code": state, "taxable_value": money(0), "gst": money(0), "rows": 0})
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
    return DashboardSummary(
        total_sales=money(total_sales),
        total_taxable_value=money(total_taxable),
        total_gst=money(igst + cgst + sgst),
        igst=money(igst),
        cgst=money(cgst),
        sgst=money(sgst),
        platform_wise_sale=[{**item, "taxable_value": money(item["taxable_value"]), "gst": money(item["gst"])} for item in platform_totals.values()],
        state_wise_sale=[{**item, "taxable_value": money(item["taxable_value"]), "gst": money(item["gst"])} for item in state_totals.values()],
        uploaded_files=uploaded_files,
        pending_errors=pending_errors,
        json_generation_status=latest_export.status if latest_export else "not_generated",
    )


@router.put("/transactions/{transaction_id}", response_model=TransactionOut)
def update_transaction(transaction_id: int, payload: TransactionUpdate, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    txn = db.get(NormalizedTransaction, transaction_id)
    if not txn or txn.user_id != user.id:
        raise HTTPException(404, "Transaction not found")
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(txn, key, value)
    db.commit()
    db.refresh(txn)
    return txn


@router.delete("/transactions/{transaction_id}")
def delete_transaction(transaction_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    txn = db.get(NormalizedTransaction, transaction_id)
    if not txn or txn.user_id != user.id:
        raise HTTPException(404, "Transaction not found")
    db.delete(txn)
    db.commit()
    return {"ok": True}


def transaction_dicts(user_id: int, profile_id: int, period: str, db: Session) -> list[dict]:
    rows = db.scalars(select(NormalizedTransaction).where(
        NormalizedTransaction.user_id == user_id,
        NormalizedTransaction.profile_id == profile_id,
        NormalizedTransaction.filing_period == period,
    )).all()
    return [TransactionOut.model_validate(row).model_dump(mode="json") for row in rows]


def validation_error_count(user_id: int, profile_id: int, period: str, db: Session) -> int:
    rows = db.scalars(select(NormalizedTransaction).where(
        NormalizedTransaction.user_id == user_id,
        NormalizedTransaction.profile_id == profile_id,
        NormalizedTransaction.filing_period == period,
        NormalizedTransaction.validation_status == "error",
    )).all()
    return len(rows)


@router.post("/gstr1/generate")
def generate_gstr1(payload: GenerateGSTR1In, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.get(GSTProfile, payload.profile_id)
    if not profile or profile.user_id != user.id:
        raise HTTPException(404, "Profile not found")
    blockers = validation_error_count(user.id, profile.id, payload.period, db)
    if blockers:
        raise HTTPException(422, f"Resolve {blockers} validation error rows before generating GSTR-1 JSON")
    rows = transaction_dicts(user.id, profile.id, payload.period, db)
    gstr = build_gstr1_json(profile.gstin, payload.period, rows)
    settings = get_settings()
    base = settings.export_dir / str(user.id) / profile.gstin / payload.period
    base.mkdir(parents=True, exist_ok=True)
    json_path = base / "gstr1.json"
    json_path.write_text(json.dumps(gstr, indent=2), encoding="utf-8")
    excel_path = write_gstr1_excel(base / "gstr1.xlsx", gstr, rows)
    export = GSTR1JsonExport(user_id=user.id, profile_id=profile.id, period=payload.period, json_path=str(json_path), excel_path=str(excel_path))
    db.add(export)
    db.add(AuditLog(user_id=user.id, action="gstr1.generate", entity_type="gstr1_json_exports"))
    db.commit()
    db.refresh(export)
    return {"status": "generated", "json": gstr, "download_json": f"/gstr1/export/{export.id}", "download_excel": f"/gstr1/export/{export.id}?format=xlsx"}


@router.get("/gstr1/history")
def gstr1_history(profile_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(GSTR1JsonExport).where(GSTR1JsonExport.user_id == user.id).order_by(GSTR1JsonExport.id.desc())
    if profile_id:
        stmt = stmt.where(GSTR1JsonExport.profile_id == profile_id)
    exports = db.scalars(stmt.limit(50)).all()
    return [{
        "id": export.id,
        "profile_id": export.profile_id,
        "period": export.period,
        "status": export.status,
        "created_at": export.created_at,
        "download_json": f"/gstr1/export/{export.id}",
        "download_excel": f"/gstr1/export/{export.id}?format=xlsx",
    } for export in exports]


@router.get("/gstr1/export/{export_id}")
def gstr1_export_download(export_id: int, format: str = "json", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    export = db.get(GSTR1JsonExport, export_id)
    if not export or export.user_id != user.id:
        raise HTTPException(404, "Export not found")
    if format == "xlsx":
        if not export.excel_path:
            raise HTTPException(404, "GSTR-1 Excel not found")
        export.status = "downloaded"
        db.commit()
        return FileResponse(export.excel_path, filename=Path(export.excel_path).name)
    if not export.json_path:
        raise HTTPException(404, "GSTR-1 JSON not found")
    export.status = "downloaded"
    db.commit()
    return FileResponse(export.json_path, filename=Path(export.json_path).name)


@router.get("/gstr1/preview/{period}")
def preview_gstr1(period: str, profile_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.get(GSTProfile, profile_id)
    if not profile or profile.user_id != user.id:
        raise HTTPException(404, "Profile not found")
    rows = transaction_dicts(user.id, profile.id, period, db)
    return build_gstr1_json(profile.gstin, period, rows)


@router.get("/gstr1/download-json/{period}")
def download_json(period: str, profile_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    export = db.scalar(select(GSTR1JsonExport).where(GSTR1JsonExport.user_id == user.id, GSTR1JsonExport.profile_id == profile_id, GSTR1JsonExport.period == period).order_by(GSTR1JsonExport.id.desc()))
    if not export or not export.json_path:
        raise HTTPException(404, "Export not found")
    export.status = "downloaded"
    db.commit()
    return FileResponse(export.json_path, filename=f"gstr1-{period}.json")


@router.get("/gstr1/download-excel/{period}")
def download_excel(period: str, profile_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    export = db.scalar(select(GSTR1JsonExport).where(GSTR1JsonExport.user_id == user.id, GSTR1JsonExport.profile_id == profile_id, GSTR1JsonExport.period == period).order_by(GSTR1JsonExport.id.desc()))
    if not export or not export.excel_path:
        raise HTTPException(404, "Export not found")
    export.status = "downloaded"
    db.commit()
    return FileResponse(export.excel_path, filename=f"gstr1-{period}.xlsx")


@router.post("/tally/company")
def tally_company(payload: TallyCompanyIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
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
    db.add(AuditLog(user_id=user.id, action="tally.company.create", entity_type="tally_company"))
    db.commit()
    db.refresh(company)
    return {"id": company.id, "company_name": company.company_name, "gstin": company.gstin, "financial_year": company.financial_year, "state": company.state, "auto_create_ledger": bool(company.auto_create_ledger)}


@router.get("/tally/companies")
def tally_companies(profile_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(TallyCompany).where(TallyCompany.user_id == user.id).order_by(TallyCompany.id.desc())
    if profile_id:
        stmt = stmt.where(TallyCompany.profile_id == profile_id)
    companies = db.scalars(stmt.limit(50)).all()
    return [{"id": company.id, "company_name": company.company_name, "gstin": company.gstin, "financial_year": company.financial_year, "state": company.state, "auto_create_ledger": bool(company.auto_create_ledger), "tally_guid": company.tally_guid} for company in companies]


@router.post("/tally/import", response_model=BatchStatus)
async def tally_import(
    platform: str,
    background_tasks: BackgroundTasks,
    profile_id: int,
    files: list[UploadFile] = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return await upload_import(platform, background_tasks, profile_id, files, user, db)


@router.get("/tally/mapping/{company_id}")
def tally_mapping(company_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    company = db.get(TallyCompany, company_id)
    if not company or company.user_id != user.id:
        raise HTTPException(404, "Company not found")
    mapping = db.scalar(select(TallyLedgerMapping).where(TallyLedgerMapping.company_id == company.id).order_by(TallyLedgerMapping.id.desc()))
    return {"company_id": company.id, "mapping": json.loads(mapping.mapping_json) if mapping else {}}


@router.post("/tally/mapping/{company_id}")
def save_tally_mapping(company_id: int, payload: dict[str, str], user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    company = db.get(TallyCompany, company_id)
    if not company or company.user_id != user.id:
        raise HTTPException(404, "Company not found")
    mapping = TallyLedgerMapping(company_id=company.id, mapping_json=json.dumps(payload))
    db.add(mapping)
    db.add(AuditLog(user_id=user.id, action="tally.mapping.save", entity_type="tally_ledger_mapping", entity_id=str(company.id)))
    db.commit()
    return {"company_id": company.id, "mapping": payload, "status": "saved"}


@router.post("/tally/generate-xml")
@router.post("/tally/generate")
def tally_xml(payload: TallyGenerateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    company = db.get(TallyCompany, payload.company_id)
    if not company or company.user_id != user.id:
        raise HTTPException(404, "Company not found")
    rows = transaction_dicts(user.id, payload.profile_id, payload.period, db)
    vouchers = build_vouchers(rows, payload.ledger_mapping)
    xml = build_tally_xml(company.company_name, rows, payload.ledger_mapping, payload.auto_create_ledgers)
    validation = validate_tally_xml(xml, vouchers)
    settings = get_settings()
    base = settings.export_dir / str(user.id) / "tally" / payload.period
    base.mkdir(parents=True, exist_ok=True)
    xml_path = base / f"tally-{payload.period}-{uuid4().hex}.xml"
    xml_path.write_text(xml, encoding="utf-8")
    excel_path = write_voucher_excel(base / f"tally-vouchers-{payload.period}-{uuid4().hex}.xlsx", vouchers)
    export = TallyExport(user_id=user.id, profile_id=payload.profile_id, company_id=company.id, period=payload.period, xml_path=str(xml_path), voucher_excel_path=str(excel_path), voucher_count=len(vouchers), validation_json=json.dumps(validation))
    db.add(export)
    db.flush()
    for voucher in vouchers:
        db.add(TallyVoucher(
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
        ))
    db.add(AuditLog(user_id=user.id, action="tally.export.generate", entity_type="tally_export", entity_id=str(export.id)))
    db.commit()
    return {"id": export.id, "voucher_count": len(vouchers), "validation": validation, "download": f"/tally/export/{export.id}", "download_excel": f"/tally/export/{export.id}?format=xlsx"}


@router.get("/tally/history")
def tally_history(profile_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(TallyExport).where(TallyExport.user_id == user.id).order_by(TallyExport.id.desc())
    if profile_id:
        stmt = stmt.where(TallyExport.profile_id == profile_id)
    exports = db.scalars(stmt.limit(50)).all()
    return [{"id": row.id, "profile_id": row.profile_id, "company_id": row.company_id, "period": row.period, "voucher_count": row.voucher_count, "status": row.status, "validation": json.loads(row.validation_json or "{}"), "created_at": row.created_at} for row in exports]


@router.get("/tally/export/{export_id}")
def tally_export_download(export_id: int, format: str = "xml", user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    export = db.get(TallyExport, export_id)
    if not export or export.user_id != user.id:
        raise HTTPException(404, "Export not found")
    if format == "xlsx":
        if not export.voucher_excel_path:
            raise HTTPException(404, "Voucher Excel not found")
        export.status = "downloaded"
        db.commit()
        return FileResponse(export.voucher_excel_path, filename=Path(export.voucher_excel_path).name)
    if not export.xml_path:
        raise HTTPException(404, "XML not found")
    export.status = "downloaded"
    db.commit()
    return FileResponse(export.xml_path, filename=Path(export.xml_path).name)


@router.get("/tally/download-xml/{export_id}")
def tally_download(export_id: str, user: User = Depends(get_current_user)):
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
    batch = ReconciliationBatch(user_id=user.id, profile_id=profile.id, status="processing")
    db.add(batch)
    db.flush()
    base = get_settings().upload_dir / str(user.id) / "reconcile" / str(batch.id)
    portal_path = save_upload(portal_file, base / "portal")
    books_path = save_upload(books_file, base / "books")
    portal_rows, portal_errors = normalize_rows(portal_path, "portal")
    book_rows, book_errors = normalize_rows(books_path, "books")
    settings = ReconSettings(tax_tolerance=money(tax_tolerance), date_tolerance_days=date_tolerance_days, enable_date_tolerance=enable_date_tolerance, enable_fuzzy_invoice=enable_fuzzy_invoice)
    result_rows, summary = reconcile(book_rows, portal_rows, settings)
    report_path = get_settings().export_dir / str(user.id) / "reconcile" / f"reconcile-{batch.id}.xlsx"
    write_reconciliation_excel(report_path, result_rows, {**summary, "parser_errors": json.dumps(portal_errors + book_errors)})
    for row in result_rows:
        db.add(ReconciliationRow(batch_id=batch.id, **row))
    batch.status = "completed_with_errors" if portal_errors or book_errors else "completed"
    batch.portal_rows = len(portal_rows)
    batch.book_rows = len(book_rows)
    batch.matched_rows = int(summary.get("matched", 0))
    batch.mismatch_rows = int(summary.get("total_rows", 0)) - batch.matched_rows
    batch.tax_difference = money(summary.get("tax_difference"))
    batch.itc_risk_amount = money(summary.get("itc_risk_amount"))
    batch.summary_json = json.dumps({**summary, "parser_errors": portal_errors + book_errors}, default=str)
    batch.report_path = str(report_path)
    db.add(ReconciliationReport(batch_id=batch.id, report_type="full", path=str(report_path)))
    db.add(AuditLog(user_id=user.id, action="reconcile.upload", entity_type="reconciliation_batch", entity_id=str(batch.id)))
    db.commit()
    db.refresh(batch)
    return {"id": batch.id, "status": batch.status, "summary": json.loads(batch.summary_json or "{}")}


@router.get("/reconcile/results/{batch_id}")
def reconcile_results(batch_id: int, category: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    batch = db.get(ReconciliationBatch, batch_id)
    if not batch or batch.user_id != user.id:
        raise HTTPException(404, "Batch not found")
    stmt = select(ReconciliationRow).where(ReconciliationRow.batch_id == batch.id).order_by(ReconciliationRow.id.asc())
    if category:
        stmt = stmt.where(ReconciliationRow.category == category)
    rows = db.scalars(stmt.limit(1000)).all()
    return {
        "id": batch.id,
        "status": batch.status,
        "summary": json.loads(batch.summary_json or "{}"),
        "categories": ["matched", "partially_matched", "invoice_mismatch", "tax_mismatch", "gstin_mismatch", "missing_in_books", "missing_in_portal", "duplicate_invoice", "invalid_gstin"],
        "rows": [{
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
        } for row in rows],
    }


@router.get("/reconcile/report/{batch_id}")
def reconcile_report(batch_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return reconcile_results(batch_id, None, user, db)


@router.get("/reconcile/history")
def reconcile_history(profile_id: int | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stmt = select(ReconciliationBatch).where(ReconciliationBatch.user_id == user.id).order_by(ReconciliationBatch.id.desc())
    if profile_id:
        stmt = stmt.where(ReconciliationBatch.profile_id == profile_id)
    batches = db.scalars(stmt.limit(50)).all()
    return [{
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
    } for batch in batches]


@router.get("/reconcile/download/{batch_id}")
def reconcile_download(batch_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    batch = db.get(ReconciliationBatch, batch_id)
    if not batch or batch.user_id != user.id:
        raise HTTPException(404, "Batch not found")
    if not batch.report_path:
        raise HTTPException(404, "Report not found")
    return FileResponse(batch.report_path, filename=f"reconciliation-{batch.id}.xlsx")
