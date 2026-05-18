from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import User
from app.utils.security import hash_password


def run_lightweight_migrations(engine) -> None:
    inspector = inspect(engine)
    if "users" in inspector.get_table_names():
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        additions = {
            "role": "VARCHAR(32) DEFAULT 'user'",
            "plan": "VARCHAR(40) DEFAULT 'free'",
            "subscription_status": "VARCHAR(32) DEFAULT 'inactive'",
            "free_access_reason": "VARCHAR(160)",
        }
        with engine.begin() as connection:
            for column, definition in additions.items():
                if column not in user_columns:
                    connection.execute(text(f"ALTER TABLE users ADD COLUMN {column} {definition}"))


def seed_super_admin() -> None:
    from app.db.session import SessionLocal

    settings = get_settings()
    db: Session = SessionLocal()
    try:
        email = settings.admin_email.lower()
        user = db.query(User).filter(User.email == email).one_or_none()
        if not user:
            user = User(
                email=email,
                password_hash=hash_password(settings.admin_password),
                full_name="Extreme Admin",
            )
            db.add(user)
            db.flush()
        user.password_hash = hash_password(settings.admin_password)
        user.full_name = user.full_name or "Extreme Admin"
        user.role = "super_admin"
        user.plan = "admin_free"
        user.subscription_status = "active"
        user.free_access_reason = "Extreme admin account with unrestricted free access"
        db.commit()
    finally:
        db.close()
