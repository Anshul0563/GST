from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi import HTTPException

from app.api.routes import create_profile, enforce_gst_profile_registration_limits, list_profiles
from app.db.session import Base
from app.models.entities import GSTProfile, User
from app.schemas.dto import GSTProfileIn


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


def test_create_profile_updates_existing_normal_user_profile_idempotently():
    Session = session_factory()
    db = Session()
    try:
        user = add_user(db, "seller@example.com")
        profile = add_profile(db, user, "07ABCDE1234F1Z5")

        saved = create_profile(
            GSTProfileIn(
                gstin="27ABCDE1234F1Z5",
                legal_name="Updated Seller",
                trade_name="Updated",
                filing_frequency="Monthly",
                financial_year="2026-27",
                return_period="082026",
            ),
            user,
            db,
        )

        assert saved.id == profile.id
        assert saved.gstin == "27ABCDE1234F1Z5"
        assert saved.state_code == "27"
        assert saved.legal_name == "Updated Seller"
        assert saved.return_period == "082026"
        assert db.query(GSTProfile).filter(GSTProfile.user_id == user.id).count() == 1
    finally:
        db.close()


def test_create_profile_updates_same_gstin_instead_of_adding_duplicate_for_admin():
    Session = session_factory()
    db = Session()
    try:
        admin = add_user(db, "admin@example.com", role="super_admin")
        profile = add_profile(db, admin, "07ABCDE1234F1Z5")

        saved = create_profile(
            GSTProfileIn(
                gstin="07ABCDE1234F1Z5",
                legal_name="Updated Same GSTIN",
                trade_name="Updated",
                filing_frequency="Monthly",
                financial_year="2026-27",
                return_period="082026",
            ),
            admin,
            db,
        )

        assert saved.id == profile.id
        assert saved.legal_name == "Updated Same GSTIN"
        assert saved.return_period == "082026"
        assert db.query(GSTProfile).filter(GSTProfile.user_id == admin.id).count() == 1
    finally:
        db.close()


def test_list_profiles_hides_same_user_duplicate_gstin_profiles():
    Session = session_factory()
    db = Session()
    try:
        user = add_user(db, "seller@example.com")
        add_profile(db, user, "07ABCDE1234F1Z5")
        add_profile(db, user, "07ABCDE1234F1Z5")

        profiles = list_profiles(user, db)

        assert len(profiles) == 1
        assert profiles[0].gstin == "07ABCDE1234F1Z5"
    finally:
        db.close()
