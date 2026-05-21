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
        transaction_constraints = inspector.get_unique_constraints("normalized_transactions")
        has_period_aware_constraint = any(
            constraint.get("column_names")
            == ["profile_id", "filing_period", "platform", "doc_type", "invoice_no", "order_item_id"]
            for constraint in transaction_constraints
        )
        if not has_period_aware_constraint and engine.dialect.name == "sqlite":
            with engine.begin() as connection:
                table_sql = connection.execute(
                    text(
                        """
                        SELECT sql
                        FROM sqlite_master
                        WHERE type = 'table' AND name = 'normalized_transactions'
                        """
                    )
                ).scalar() or ""
            has_period_aware_constraint = "uq_txn_doc_item_period" in table_sql
        if not has_period_aware_constraint and engine.dialect.name == "sqlite":
            with engine.begin() as connection:
                connection.execute(text("PRAGMA foreign_keys=OFF"))
                connection.execute(
                    text(
                        """
                        CREATE TABLE normalized_transactions_new (
                            id INTEGER NOT NULL,
                            user_id INTEGER NOT NULL,
                            profile_id INTEGER NOT NULL,
                            batch_id INTEGER,
                            platform VARCHAR(40) NOT NULL,
                            gstin VARCHAR(15) NOT NULL,
                            etin VARCHAR(15),
                            filing_period VARCHAR(6) NOT NULL,
                            order_id VARCHAR(120),
                            order_item_id VARCHAR(120),
                            invoice_no VARCHAR(120),
                            invoice_date DATE,
                            document_date DATE,
                            doc_type VARCHAR(20) NOT NULL,
                            buyer_state_code VARCHAR(2),
                            buyer_state_name VARCHAR(80),
                            hsn VARCHAR(20),
                            product_name VARCHAR(255),
                            sku VARCHAR(120),
                            qty NUMERIC(14, 3) NOT NULL,
                            taxable_value NUMERIC(14, 2) NOT NULL,
                            gst_rate NUMERIC(6, 2) NOT NULL,
                            igst NUMERIC(14, 2) NOT NULL,
                            cgst NUMERIC(14, 2) NOT NULL,
                            sgst NUMERIC(14, 2) NOT NULL,
                            cess NUMERIC(14, 2) NOT NULL,
                            tcs NUMERIC(14, 2) NOT NULL,
                            tds NUMERIC(14, 2) NOT NULL,
                            gross_amount NUMERIC(14, 2) NOT NULL,
                            discount_seller NUMERIC(14, 2) NOT NULL,
                            discount_platform NUMERIC(14, 2) NOT NULL,
                            settlement_amount NUMERIC(14, 2) NOT NULL,
                            source_file VARCHAR(255),
                            raw_row_json TEXT,
                            validation_status VARCHAR(20) NOT NULL,
                            validation_errors TEXT,
                            created_at DATETIME NOT NULL,
                            PRIMARY KEY (id),
                            CONSTRAINT uq_txn_doc_item_period UNIQUE (
                                profile_id,
                                filing_period,
                                platform,
                                doc_type,
                                invoice_no,
                                order_item_id
                            ),
                            FOREIGN KEY(user_id) REFERENCES users (id),
                            FOREIGN KEY(profile_id) REFERENCES gst_profiles (id),
                            FOREIGN KEY(batch_id) REFERENCES platform_import_batches (id)
                        )
                        """
                    )
                )
                connection.execute(
                    text(
                        """
                        INSERT INTO normalized_transactions_new (
                            id, user_id, profile_id, batch_id, platform, gstin, etin,
                            filing_period, order_id, order_item_id, invoice_no,
                            invoice_date, document_date, doc_type, buyer_state_code,
                            buyer_state_name, hsn, product_name, sku, qty,
                            taxable_value, gst_rate, igst, cgst, sgst, cess, tcs,
                            tds, gross_amount, discount_seller, discount_platform,
                            settlement_amount, source_file, raw_row_json,
                            validation_status, validation_errors, created_at
                        )
                        SELECT
                            id, user_id, profile_id, batch_id, platform, gstin, etin,
                            filing_period, order_id, order_item_id, invoice_no,
                            invoice_date, document_date, doc_type, buyer_state_code,
                            buyer_state_name, hsn, product_name, sku, qty,
                            taxable_value, gst_rate, igst, cgst, sgst, cess, tcs,
                            tds, gross_amount, discount_seller, discount_platform,
                            settlement_amount, source_file, raw_row_json,
                            validation_status, validation_errors, created_at
                        FROM normalized_transactions
                        """
                    )
                )
                connection.execute(text("DROP TABLE normalized_transactions"))
                connection.execute(text("ALTER TABLE normalized_transactions_new RENAME TO normalized_transactions"))
                for column in (
                    "batch_id",
                    "buyer_state_code",
                    "etin",
                    "filing_period",
                    "gstin",
                    "invoice_no",
                    "platform",
                    "profile_id",
                    "user_id",
                ):
                    connection.execute(
                        text(
                            f"CREATE INDEX ix_normalized_transactions_{column} "
                            f"ON normalized_transactions ({column})"
                        )
                    )
                connection.execute(text("PRAGMA foreign_keys=ON"))


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
