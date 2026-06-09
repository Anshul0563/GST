from pathlib import Path

from app.db.session import APP_ROOT, normalize_database_url


def test_relative_sqlite_database_url_is_anchored_to_api_root():
    normalized = normalize_database_url("sqlite:///./gst_bharat.db")

    assert normalized == f"sqlite:///{(APP_ROOT / 'gst_bharat.db').resolve()}"


def test_absolute_sqlite_database_url_is_preserved(tmp_path: Path):
    database = tmp_path / "gst_bharat.db"

    assert normalize_database_url(f"sqlite:///{database}") == f"sqlite:///{database}"


def test_postgres_database_url_uses_psycopg_driver():
    assert (
        normalize_database_url("postgres://user:pass@host:5432/gst_bharat")
        == "postgresql+psycopg://user:pass@host:5432/gst_bharat"
    )
