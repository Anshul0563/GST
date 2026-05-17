from datetime import datetime
from pathlib import Path
import json
import shutil
from uuid import uuid4

from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response
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
from app.services.validation import validate_gstin
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

