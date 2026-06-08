from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException

from app.api.routes import enforce_gst_profile_registration_limits
from app.db.session import Base
from app.models.entities import GSTProfile, User


def session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def add_user(db, email: str, role: str = "user") -> User:
    user = User(
        email=email,
        password_hash="x",
        full_name=email,
        role=role,
        plan="free",
        subscription_status="inactive",
    )
    db.add(user)
    db.flush()
    return user


def add_profile(db, user: User, gstin: str = "07ABCDE1234F1Z5") -> GSTProfile:
    profile = GSTProfile(
        user_id=user.id,
        gstin=gstin,
        legal_name="Demo Seller",
        trade_name="Demo",
        state_code=gstin[:2],
        filing_frequency="Monthly",
        financial_year="2026-27",
        return_period="042026",
    )
    db.add(profile)
    db.flush()
    return profile


def assert_limit_error(func, message: str) -> None:
    try:
        func()
    except HTTPException as exc:
        assert exc.status_code == 409
        assert exc.detail == message
    else:
        raise AssertionError("Expected profile limit HTTPException")


def test_normal_user_can_register_only_one_gstin_on_same_account():
    Session = session_factory()
    db = Session()
    try:
        user = add_user(db, "seller@example.com")
        add_profile(db, user)

        assert_limit_error(
            lambda: enforce_gst_profile_registration_limits(
                user,
                db,
                gstin="27ABCDE1234F1Z5",
            ),
            "Only one GSTIN can be registered per user account.",
        )
    finally:
        db.close()


def test_same_gstin_cannot_be_registered_from_another_normal_account():
    Session = session_factory()
    db = Session()
    try:
        owner = add_user(db, "owner@example.com")
        other = add_user(db, "other@example.com")
        add_profile(db, owner, "07ABCDE1234F1Z5")

        assert_limit_error(
            lambda: enforce_gst_profile_registration_limits(
                other,
                db,
                gstin="07ABCDE1234F1Z5",
            ),
            "This GSTIN is already registered with another account.",
        )
    finally:
        db.close()


def test_normal_user_cannot_update_profile_to_duplicate_gstin():
    Session = session_factory()
    db = Session()
    try:
        owner = add_user(db, "owner@example.com")
        other = add_user(db, "other@example.com")
        add_profile(db, owner, "07ABCDE1234F1Z5")
        other_profile = add_profile(db, other, "27ABCDE1234F1Z5")

        assert_limit_error(
            lambda: enforce_gst_profile_registration_limits(
                other,
                db,
                gstin="07ABCDE1234F1Z5",
                current_profile_id=other_profile.id,
            ),
            "This GSTIN is already registered with another account.",
        )
    finally:
        db.close()


def test_super_admin_bypasses_gstin_profile_limits():
    Session = session_factory()
    db = Session()
    try:
        owner = add_user(db, "owner@example.com")
        admin = add_user(db, "admin@example.com", role="super_admin")
        add_profile(db, owner, "07ABCDE1234F1Z5")
        add_profile(db, admin, "27ABCDE1234F1Z5")

        enforce_gst_profile_registration_limits(
            admin,
            db,
            gstin="07ABCDE1234F1Z5",
        )
    finally:
        db.close()
