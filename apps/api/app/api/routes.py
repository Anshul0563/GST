from datetime import datetime
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
    PlatformImportBatch,
    ReconciliationBatch,
    TallyCompany,
    UploadedFile,
    User,
)
from app.parsers.factory import get_parser
from app.schemas.dto import (
    BatchStatus,
    DashboardSummary,
    GSTProfileIn,
    GSTProfileOut,
    GenerateGSTR1In,
    LoginIn,
    RegisterIn,
    TallyCompanyIn,
    TallyGenerateIn,
    Token,
    TransactionOut,
    TransactionUpdate,
)
from app.services.excel_export import write_gstr1_excel
from app.services.gst import build_gstr1_json
from app.services.tally import build_tally_xml
from app.services.transaction_normalizer import finalize_transaction
from app.services.validation import money, validate_gstin
from app.utils.security import create_access_token, hash_password, verify_password


router = APIRouter()
ALLOWED_EXTENSIONS = {".xlsx", ".xlsm", ".xls", ".csv"}


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
    return {"id": user.id, "email": user.email, "full_name": user.full_name}


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
        for txn in result.transactions:
            duplicate = db.scalar(select(NormalizedTransaction).where(
                NormalizedTransaction.profile_id == batch.profile_id,
                NormalizedTransaction.platform == txn.get("platform"),
                NormalizedTransaction.invoice_no == txn.get("invoice_no"),
                NormalizedTransaction.order_item_id == txn.get("order_item_id"),
            ))
            if duplicate:
                result.errors.append({"error": "Duplicate invoice/order item skipped", "invoice_no": txn.get("invoice_no"), "order_item_id": txn.get("order_item_id")})
                continue
            db.add(NormalizedTransaction(user_id=batch.user_id, profile_id=batch.profile_id, batch_id=batch.id, **txn))
        batch.parsed_rows = len(result.transactions)
        batch.error_rows = len(result.errors) + sum(1 for txn in result.transactions if txn.get("validation_status") == "error")
        batch.error_report_json = json.dumps(result.errors)
        batch.status = "completed" if not result.errors else "completed_with_errors"
        batch.completed_at = datetime.utcnow()
        db.add(AuditLog(user_id=batch.user_id, action="import.processed", entity_type="platform_import_batch", entity_id=str(batch.id)))
        db.commit()
    except Exception as exc:
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
    return BatchStatus(id=batch.id, platform=batch.platform, status=batch.status, parsed_rows=batch.parsed_rows, error_rows=batch.error_rows, errors=json.loads(batch.error_report_json or "[]"))


@router.get("/imports/{batch_id}/errors")
def import_errors(batch_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    batch = db.get(PlatformImportBatch, batch_id)
    if not batch or batch.user_id != user.id:
        raise HTTPException(404, "Batch not found")
    rows = db.scalars(select(NormalizedTransaction).where(NormalizedTransaction.batch_id == batch_id, NormalizedTransaction.validation_status == "error")).all()
    return {"parser_errors": json.loads(batch.error_report_json or "[]"), "row_errors": [TransactionOut.model_validate(row).model_dump(mode="json") for row in rows]}


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
    uploaded_files = len(db.scalars(select(UploadedFile).where(UploadedFile.user_id == user.id)).all())
    latest_export = db.scalar(select(GSTR1JsonExport).where(GSTR1JsonExport.user_id == user.id).order_by(GSTR1JsonExport.id.desc()))
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


@router.post("/gstr1/generate")
def generate_gstr1(payload: GenerateGSTR1In, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.get(GSTProfile, payload.profile_id)
    if not profile or profile.user_id != user.id:
        raise HTTPException(404, "Profile not found")
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
    return {"status": "generated", "json": gstr, "download_json": f"/gstr1/download-json/{payload.period}?profile_id={profile.id}", "download_excel": f"/gstr1/download-excel/{payload.period}?profile_id={profile.id}"}


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
    return FileResponse(export.json_path, filename=f"gstr1-{period}.json")


@router.get("/gstr1/download-excel/{period}")
def download_excel(period: str, profile_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    export = db.scalar(select(GSTR1JsonExport).where(GSTR1JsonExport.user_id == user.id, GSTR1JsonExport.profile_id == profile_id, GSTR1JsonExport.period == period).order_by(GSTR1JsonExport.id.desc()))
    if not export or not export.excel_path:
        raise HTTPException(404, "Export not found")
    return FileResponse(export.excel_path, filename=f"gstr1-{period}.xlsx")


@router.post("/tally/company")
def tally_company(payload: TallyCompanyIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.get(GSTProfile, payload.profile_id)
    if not profile or profile.user_id != user.id:
        raise HTTPException(404, "Profile not found")
    company = TallyCompany(user_id=user.id, profile_id=profile.id, company_name=payload.company_name, tally_guid=payload.tally_guid)
    db.add(company)
    db.commit()
    db.refresh(company)
    return {"id": company.id, "company_name": company.company_name}


@router.post("/tally/generate-xml")
def tally_xml(payload: TallyGenerateIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    company = db.get(TallyCompany, payload.company_id)
    if not company or company.user_id != user.id:
        raise HTTPException(404, "Company not found")
    rows = transaction_dicts(user.id, payload.profile_id, payload.period, db)
    xml = build_tally_xml(company.company_name, rows, payload.ledger_mapping)
    path = get_settings().export_dir / str(user.id) / f"tally-{payload.period}-{uuid4().hex}.xml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(xml, encoding="utf-8")
    return {"id": path.stem, "download": f"/tally/download-xml/{path.name}"}


@router.get("/tally/download-xml/{export_id}")
def tally_download(export_id: str, user: User = Depends(get_current_user)):
    path = get_settings().export_dir / str(user.id) / export_id
    if not path.exists():
        raise HTTPException(404, "Export not found")
    return FileResponse(path, filename=export_id)


@router.post("/reconcile/upload")
async def reconcile_upload(profile_id: int, portal_file: UploadFile = File(...), books_file: UploadFile = File(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile = db.get(GSTProfile, profile_id)
    if not profile or profile.user_id != user.id:
        raise HTTPException(404, "Profile not found")
    batch = ReconciliationBatch(user_id=user.id, profile_id=profile.id, status="completed")
    db.add(batch)
    db.commit()
    db.refresh(batch)
    return {"id": batch.id, "status": "completed", "summary": {"matched": 0, "amount_mismatch": 0, "invoice_mismatch": 0, "missing_in_2b": 0, "missing_in_books": 0, "pending": 0}}


@router.get("/reconcile/report/{batch_id}")
def reconcile_report(batch_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    batch = db.get(ReconciliationBatch, batch_id)
    if not batch or batch.user_id != user.id:
        raise HTTPException(404, "Batch not found")
    return {"id": batch.id, "status": batch.status, "categories": ["Matched", "Amount mismatch", "Invoice mismatch", "Missing in 2B", "Missing in books", "Pending"]}


@router.get("/reconcile/download/{batch_id}")
def reconcile_download(batch_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    batch = db.get(ReconciliationBatch, batch_id)
    if not batch or batch.user_id != user.id:
        raise HTTPException(404, "Batch not found")
    return JSONResponse({"message": "Reconciliation Excel generation hook is ready", "batch_id": batch.id})
