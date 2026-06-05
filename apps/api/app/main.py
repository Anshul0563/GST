from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routes import router
from app.core.config import get_settings
from app.db.bootstrap import run_lightweight_migrations, seed_super_admin
from app.db.session import Base, SessionLocal, engine
from app.models import entities

Base.metadata.create_all(bind=engine)
run_lightweight_migrations(engine)
seed_super_admin()

app = FastAPI(title="GST Bharat API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "GST Bharat API"}


@app.get("/health/readiness")
def readiness():
    settings = get_settings()
    db_ok = False
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
        db_ok = True
    return {
        "status": "ready" if db_ok else "degraded",
        "database": "ok" if db_ok else "error",
        "razorpay": {
            "orders": bool(settings.razorpay_key_id and settings.razorpay_key_secret),
            "webhooks": bool(settings.razorpay_webhook_secret),
            "key_id_prefix": (
                f"{settings.razorpay_key_id[:8]}..."
                if settings.razorpay_key_id
                else None
            ),
        },
        "storage": {
            "upload_dir": str(settings.upload_dir),
            "export_dir": str(settings.export_dir),
        },
    }
