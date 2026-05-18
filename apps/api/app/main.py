from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.db.bootstrap import run_lightweight_migrations, seed_super_admin
from app.db.session import Base, engine
from app.models import entities


Base.metadata.create_all(bind=engine)
run_lightweight_migrations(engine)
seed_super_admin()

app = FastAPI(title="GST Bharat API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "GST Bharat API"}
