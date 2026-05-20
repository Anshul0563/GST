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
    if "tally_companies" in inspector.get_table_names():
        tally_columns = {column["name"] for column in inspector.get_columns("tally_companies")}
        additions = {
            "gstin": "VARCHAR(15)",
            "financial_year": "VARCHAR(9)",
            "state": "VARCHAR(80)",
            "auto_create_ledger": "INTEGER DEFAULT 1",
        }
        with engine.begin() as connection:
            for column, definition in additions.items():
                if column not in tally_columns:
                    connection.execute(text(f"ALTER TABLE tally_companies ADD COLUMN {column} {definition}"))
    if "reconciliation_batches" in inspector.get_table_names():
        batch_columns = {column["name"] for column in inspector.get_columns("reconciliation_batches")}
        additions = {
            "portal_rows": "INTEGER DEFAULT 0",
            "book_rows": "INTEGER DEFAULT 0",
            "matched_rows": "INTEGER DEFAULT 0",
            "mismatch_rows": "INTEGER DEFAULT 0",
            "tax_difference": "NUMERIC(14, 2) DEFAULT 0",
            "itc_risk_amount": "NUMERIC(14, 2) DEFAULT 0",
            "summary_json": "TEXT",
        }
        with engine.begin() as connection:
            for column, definition in additions.items():
                if column not in batch_columns:
                    connection.execute(text(f"ALTER TABLE reconciliation_batches ADD COLUMN {column} {definition}"))
    if "reconciliation_rows" in inspector.get_table_names():
        row_columns = {column["name"] for column in inspector.get_columns("reconciliation_rows")}
        additions = {
            "taxable_value": "NUMERIC(14, 2) DEFAULT 0",
            "igst": "NUMERIC(14, 2) DEFAULT 0",
            "cgst": "NUMERIC(14, 2) DEFAULT 0",
            "sgst": "NUMERIC(14, 2) DEFAULT 0",
            "total_tax": "NUMERIC(14, 2) DEFAULT 0",
            "tax_difference": "NUMERIC(14, 2) DEFAULT 0",
            "match_score": "NUMERIC(6, 2) DEFAULT 0",
            "mismatch_reason": "VARCHAR(255)",
        }
        with engine.begin() as connection:
            for column, definition in additions.items():
                if column not in row_columns:
                    connection.execute(text(f"ALTER TABLE reconciliation_rows ADD COLUMN {column} {definition}"))
    if "platform_import_batches" in inspector.get_table_names():
        import_columns = {column["name"] for column in inspector.get_columns("platform_import_batches")}
        with engine.begin() as connection:
            if "period" not in import_columns:
                connection.execute(text("ALTER TABLE platform_import_batches ADD COLUMN period VARCHAR(6)"))
                connection.execute(
                    text(
                        """
                        UPDATE platform_import_batches
                        SET period = (
                            SELECT return_period
                            FROM gst_profiles
                            WHERE gst_profiles.id = platform_import_batches.profile_id
                        )
                        WHERE period IS NULL OR period = ''
                        """
                    )
                )
    if "normalized_transactions" in inspector.get_table_names():
        transaction_columns = {column["name"] for column in inspector.get_columns("normalized_transactions")}
        with engine.begin() as connection:
            if "document_date" not in transaction_columns:
                connection.execute(text("ALTER TABLE normalized_transactions ADD COLUMN document_date DATE"))
                connection.execute(
                    text(
                        """
                        UPDATE normalized_transactions
                        SET document_date = invoice_date
                        WHERE document_date IS NULL
                        """
                    )
                )


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
