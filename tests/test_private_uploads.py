from io import BytesIO
import importlib
from pathlib import Path
import stat

import pytest
from werkzeug.datastructures import FileStorage
from werkzeug.security import generate_password_hash


@pytest.fixture()
def app(tmp_path, monkeypatch):
    database = tmp_path / "homebridge-test.sqlite"
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database}")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@test.homebridge")
    monkeypatch.setenv("ADMIN_PASSWORD", "test-admin-password-12345")
    monkeypatch.setenv("ADMIN_NAME", "Test Admin")

    import config
    importlib.reload(config)

    from app import create_app
    from app.models import db

    application = create_app()

    application.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        UPLOAD_FOLDER=str(tmp_path / "public"),
        PRIVATE_UPLOAD_FOLDER=str(tmp_path / "private"),
    )
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


def _add_payment(app, proof_file):
    from app.models import Payment, User, db

    with app.app_context():
        student = User(
            name="Test Student",
            email="student@test.homebridge",
            password=generate_password_hash("student-password-123"),
            role="student",
            is_approved=True,
        )
        db.session.add(student)
        db.session.flush()
        payment = Payment(
            user_id=student.id,
            payment_type="student_service_fee",
            amount=10,
            currency="USD",
            reference="TEST-REF-001",
            proof_file=proof_file,
            status="pending",
        )
        db.session.add(payment)
        db.session.commit()
        return payment.id


def test_payment_receipt_is_stored_outside_public_uploads(app):
    from app.private_uploads import store_platform_payment_proof

    with app.app_context():
        receipt = FileStorage(
            stream=BytesIO(b"%PDF-1.7 test receipt"),
            filename="receipt.pdf",
            content_type="application/pdf",
        )
        relative_path = store_platform_payment_proof(receipt)
        saved = Path(app.config["PRIVATE_UPLOAD_FOLDER"]) / relative_path

        assert relative_path.startswith("platform-payments/")
        assert saved.is_file()
        assert not str(saved).startswith(app.config["UPLOAD_FOLDER"])
        assert stat.S_IMODE(saved.stat().st_mode) == 0o600
        assert stat.S_IMODE(saved.parent.stat().st_mode) == 0o700


def test_payment_receipt_rejects_mismatched_file_signature(app):
    from app.private_uploads import store_platform_payment_proof

    with app.app_context():
        receipt = FileStorage(stream=BytesIO(b"not a PDF"), filename="receipt.pdf")
        with pytest.raises(ValueError, match="does not match"):
            store_platform_payment_proof(receipt)


def test_payment_receipt_rejects_unsupported_extension(app):
    from app.private_uploads import store_platform_payment_proof

    with app.app_context():
        receipt = FileStorage(stream=BytesIO(b"MZ executable"), filename="receipt.exe")
        with pytest.raises(ValueError, match="Upload a PDF"):
            store_platform_payment_proof(receipt)


def test_public_upload_route_denies_legacy_payment_proof_path(app):
    _add_payment(app, "proofs/legacy-receipt.pdf")
    client = app.test_client()
    assert client.get("/uploads/proofs/legacy-receipt.pdf").status_code == 404
    assert client.get("/static/uploads/proofs/legacy-receipt.pdf").status_code == 404


def test_only_admin_can_download_platform_payment_proof(app):
    from app.models import Payment, db

    with app.app_context():
        private_root = Path(app.config["PRIVATE_UPLOAD_FOLDER"]) / "platform-payments"
        private_root.mkdir(parents=True)
        (private_root / "payment-test.pdf").write_bytes(b"%PDF-1.7 private receipt")
        payment_id = _add_payment(app, "platform-payments/payment-test.pdf")

    anonymous = app.test_client()
    assert anonymous.get(f"/admin/payments/{payment_id}/proof").status_code == 302

    from app.models import User

    from werkzeug.security import check_password_hash

    with app.app_context():
        student_id = User.query.filter_by(email="student@test.homebridge").one().id
        admin_user = User.query.filter_by(email="admin@test.homebridge").one()
        admin_id = admin_user.id
        assert check_password_hash(admin_user.password, "test-admin-password-12345")
        assert admin_user.is_active is True
        assert admin_user.is_active_account is True

    student = app.test_client()
    student_login = student.post("/login", data={
        "email": "student@test.homebridge",
        "password": "student-password-123",
    })
    assert student_login.status_code == 302
    with student.session_transaction() as session:
        assert session.get("_user_id") == str(student_id)
    assert student.get(f"/admin/payments/{payment_id}/proof").status_code == 302

    admin = app.test_client()
    admin_login = admin.post("/login", data={
        "email": "admin@test.homebridge",
        "password": "test-admin-password-12345",
    })
    assert admin_login.status_code == 302, f"admin login failed: {admin_login.location}"
    assert admin_login.location.endswith("/dashboard"), f"admin credentials rejected: {admin_login.location}"
    with admin.session_transaction() as session:
        assert session.get("_user_id") == str(admin_id)
    response = admin.get(f"/admin/payments/{payment_id}/proof")
    assert response.status_code == 200
    assert response.data.startswith(b"%PDF-")


def test_property_image_upload_reencodes_valid_image(app):
    from PIL import Image
    from app.media_uploads import store_property_image

    buffer = BytesIO()
    Image.new("RGB", (2, 2), color=(20, 40, 60)).save(buffer, format="PNG")
    buffer.seek(0)
    with app.app_context():
        app.config["UPLOAD_FOLDER"] = str(Path(app.config["UPLOAD_FOLDER"]))
        uploaded = FileStorage(stream=buffer, filename="house.png", content_type="image/png")
        relative = store_property_image(uploaded)
        saved = Path(app.config["UPLOAD_FOLDER"]) / relative
        assert relative.startswith("properties/property-")
        assert saved.is_file()
        with Image.open(saved) as check:
            assert check.format == "PNG"
            assert check.size == (2, 2)


def test_property_image_upload_rejects_fake_image(app):
    from app.media_uploads import store_property_image

    with app.app_context():
        uploaded = FileStorage(
            stream=BytesIO(b"<script>alert(1)</script>"),
            filename="house.png",
            content_type="image/png",
        )
        with pytest.raises(ValueError, match="not a valid image"):
            store_property_image(uploaded)


def test_production_startup_requires_secret_and_database(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.delenv("SECRET_KEY", raising=False)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from app import create_app

    with pytest.raises(RuntimeError, match="SECRET_KEY, DATABASE_URL"):
        create_app()


def test_production_startup_rejects_short_secret(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "too-short")
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused:unused@127.0.0.1/unused")
    monkeypatch.setenv("PRIVATE_UPLOAD_FOLDER", "/var/lib/homebridge/private-uploads")
    from app import create_app

    with pytest.raises(RuntimeError, match="at least 32 characters"):
        create_app()



def test_csrf_rejects_public_post_without_token(app):
    app.config["WTF_CSRF_ENABLED"] = True
    response = app.test_client().post("/inquire", data={
        "visitor_name": "Test Visitor",
        "visitor_email": "visitor@example.test",
        "message": "Please contact me.",
    })
    assert response.status_code == 400


def test_all_post_forms_include_csrf_tokens():
    import re

    for template in Path("app/templates").rglob("*.html"):
        content = template.read_text(encoding="utf-8")
        for match in re.finditer(r"<form\b[^>]*>", content, flags=re.IGNORECASE | re.DOTALL):
            opening_tag = match.group(0)
            if not re.search(r"\bmethod\s*=\s*[\"']?post\b", opening_tag, flags=re.IGNORECASE):
                continue
            closing = content.find("</form>", match.end())
            assert closing >= 0, f"Unclosed form in {template}"
            body = content[match.end():closing]
            assert 'name="csrf_token"' in body, f"Missing CSRF token in {template}"


def test_logout_cannot_be_triggered_with_get(app):
    response = app.test_client().get("/logout")
    assert response.status_code == 405



def test_rent_payment_proof_is_scoped_to_tenant_and_property_landlord(app):
    from datetime import date
    from decimal import Decimal
    from app.models import Property, RentPayment, Tenancy, User, db

    password = "role-test-password-123"
    with app.app_context():
        landlord_one = User(name="Landlord One", email="landlord-one@test.homebridge",
                            password=generate_password_hash(password), role="landlord",
                            is_approved=True)
        landlord_two = User(name="Landlord Two", email="landlord-two@test.homebridge",
                            password=generate_password_hash(password), role="landlord",
                            is_approved=True)
        student_one = User(name="Student One", email="student-one@test.homebridge",
                           password=generate_password_hash(password), role="student",
                           is_approved=True)
        student_two = User(name="Student Two", email="student-two@test.homebridge",
                           password=generate_password_hash(password), role="student",
                           is_approved=True)
        db.session.add_all([landlord_one, landlord_two, student_one, student_two])
        db.session.flush()

        prop = Property(
            landlord_id=landlord_one.id,
            title="Test rental",
            price=Decimal("500.00"),
            location="Test Street",
            city="Harare",
            country="Zimbabwe",
        )
        db.session.add(prop)
        db.session.flush()

        tenancy = Tenancy(
            property_id=prop.id,
            student_id=student_one.id,
            rent_amount=Decimal("500.00"),
            rent_currency="USD",
            rent_period="month",
            start_date=date.today(),
            status="active",
        )
        db.session.add(tenancy)
        db.session.flush()

        payment = RentPayment(
            tenancy_id=tenancy.id,
            property_id=prop.id,
            student_id=student_one.id,
            amount=Decimal("500.00"),
            currency="USD",
            payment_month=date.today().strftime("%Y-%m"),
            proof_file="rent-payments/receipt.pdf",
            status="pending",
        )
        db.session.add(payment)
        db.session.commit()
        payment_id = payment.id

    private_folder = Path(app.config["PRIVATE_UPLOAD_FOLDER"]) / "rent-payments"
    private_folder.mkdir(parents=True, exist_ok=True)
    (private_folder / "receipt.pdf").write_bytes(b"%PDF-1.7 rent receipt")

    def logged_in_client(email):
        client = app.test_client()
        response = client.post("/login", data={"email": email, "password": password})
        assert response.status_code == 302
        return client

    student_owner = logged_in_client("student-one@test.homebridge")
    student_other = logged_in_client("student-two@test.homebridge")
    landlord_owner = logged_in_client("landlord-one@test.homebridge")
    landlord_other = logged_in_client("landlord-two@test.homebridge")

    assert student_owner.get(f"/student/rent-payments/{payment_id}/proof").status_code == 200
    assert student_other.get(f"/student/rent-payments/{payment_id}/proof").status_code == 404
    assert landlord_owner.get(f"/landlord/rent-payments/{payment_id}/proof").status_code == 200
    assert landlord_other.get(f"/landlord/rent-payments/{payment_id}/proof").status_code == 404



def test_admin_platform_payment_confirmation_notifies_payer(app):
    from app.models import Notification, Payment, User, db

    payment_id = _add_payment(app, "platform-payments/confirmation-proof.pdf")
    with app.app_context():
        student_id = User.query.filter_by(email="student@test.homebridge").one().id

    admin = app.test_client()
    login = admin.post("/login", data={
        "email": "admin@test.homebridge",
        "password": "test-admin-password-12345",
    })
    assert login.status_code == 302
    response = admin.post(f"/admin/confirm-payment/{payment_id}")
    assert response.status_code == 302

    with app.app_context():
        payment = db.session.get(Payment, payment_id)
        notice = Notification.query.filter_by(
            user_id=student_id,
            event_type="platform_payment_confirmed",
        ).one()
        assert payment.status == "confirmed"
        assert notice.target_url == "/student/service-fee"



def test_private_upload_folder_cannot_be_inside_public_static(monkeypatch, tmp_path):
    import importlib

    public_static_child = Path(__file__).resolve().parents[1] / "app" / "static" / "uploads" / "private"
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'private-path-test.sqlite'}")
    monkeypatch.setenv("PRIVATE_UPLOAD_FOLDER", str(public_static_child))

    import config
    importlib.reload(config)
    from app import create_app

    with pytest.raises(RuntimeError, match="outside the public static directory"):
        create_app()



def test_landlord_offer_student_acceptance_creates_one_tenancy(app):
    from datetime import date, datetime, timedelta
    from decimal import Decimal
    from app.models import (
        Application, Notification, Property, Tenancy, TenancyOffer,
        User, ViewingAppointment, db,
    )

    password = "tenancy-flow-password-123"
    with app.app_context():
        landlord = User(
            name="Offer Landlord",
            email="offer-landlord@test.homebridge",
            password=generate_password_hash(password),
            role="landlord",
            is_approved=True,
        )
        student = User(
            name="Offer Student",
            email="offer-student@test.homebridge",
            password=generate_password_hash(password),
            role="student",
            is_approved=True,
        )
        db.session.add_all([landlord, student])
        db.session.flush()
        student_id = student.id

        prop = Property(
            landlord_id=landlord.id,
            title="Student room near campus",
            price=Decimal("400.00"),
            location="Campus Road",
            city="Harare",
            country="Zimbabwe",
            is_verified=True,
            is_published=True,
        )
        db.session.add(prop)
        db.session.flush()

        application = Application(
            property_id=prop.id,
            student_id=student.id,
            status="approved",
            message="I am interested in this room.",
        )
        db.session.add(application)
        db.session.flush()

        viewing = ViewingAppointment(
            application_id=application.id,
            proposed_by_id=landlord.id,
            scheduled_at=datetime.now() + timedelta(days=1),
            meeting_details="Meet at the property entrance.",
            status="confirmed",
        )
        db.session.add(viewing)
        db.session.commit()
        application_id = application.id
        landlord_id = landlord.id

    landlord_client = app.test_client()
    assert landlord_client.post("/login", data={
        "email": "offer-landlord@test.homebridge",
        "password": password,
    }).status_code == 302

    start = date.today() + timedelta(days=1)
    end = start + timedelta(days=180)
    offer_response = landlord_client.post(
        f"/landlord/applications/{application_id}/tenancy-offer",
        data={
            "rent_amount": "400.00",
            "rent_currency": "USD",
            "rent_period": "month",
            "room_label": "Room A",
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "terms": "Rent due monthly.",
        },
    )
    assert offer_response.status_code == 302

    with app.app_context():
        offer = TenancyOffer.query.filter_by(application_id=application_id).one()
        assert offer.status == "proposed"
        offer_id = offer.id
        assert Notification.query.filter_by(
            user_id=student_id,
            event_type="tenancy_offer",
        ).count() == 1

    student_client = app.test_client()
    assert student_client.post("/login", data={
        "email": "offer-student@test.homebridge",
        "password": password,
    }).status_code == 302

    accept_response = student_client.post(
        f"/student/applications/{application_id}/tenancy-offer/respond",
        data={"response": "accepted"},
    )
    assert accept_response.status_code == 302

    # Replaying acceptance must not create a second tenancy.
    student_client.post(
        f"/student/applications/{application_id}/tenancy-offer/respond",
        data={"response": "accepted"},
    )

    with app.app_context():
        offer = db.session.get(TenancyOffer, offer_id)
        tenancies = Tenancy.query.filter_by(application_id=application_id).all()
        assert offer.status == "accepted"
        assert len(tenancies) == 1
        assert tenancies[0].student_id == student_id
        assert tenancies[0].rent_amount == Decimal("400.00")
        assert tenancies[0].rent_currency == "USD"
        assert Notification.query.filter_by(
            user_id=landlord_id,
            event_type="tenancy_offer_accepted",
        ).count() == 1



def test_release_migration_covers_all_new_production_tables():
    migration = Path("migrations/20261120_agreements_notifications.sql").read_text(encoding="utf-8")
    for table in ("property_local_details", "rental_agreement", "notification"):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in migration
    for column in ("period_start", "period_end", "reviewed_by_id", "reviewed_at", "review_notes", "cost_currency"):
        assert column in migration



def test_platform_payment_receipt_rejects_oversized_file(app):
    from app.private_uploads import store_platform_payment_proof

    with app.app_context():
        receipt = FileStorage(
            stream=BytesIO(b"%PDF-" + (b"x" * (10 * 1024 * 1024))),
            filename="large-receipt.pdf",
        )
        with pytest.raises(ValueError, match="10 MB"):
            store_platform_payment_proof(receipt)


def test_signed_agreement_rejects_invalid_pdf_signature(app):
    from types import SimpleNamespace
    from app.agreement_workflow import store_signed_pdf

    with app.app_context():
        upload = FileStorage(stream=BytesIO(b"not a PDF"), filename="signed.pdf")
        agreement = SimpleNamespace(status="ready_for_signing")
        with pytest.raises(ValueError, match="valid PDF"):
            store_signed_pdf(agreement, upload, uploader_id=1)


def test_signed_agreement_rejects_oversized_pdf(app):
    from types import SimpleNamespace
    from app.agreement_workflow import store_signed_pdf

    with app.app_context():
        upload = FileStorage(
            stream=BytesIO(b"%PDF-" + (b"x" * (15 * 1024 * 1024))),
            filename="signed.pdf",
        )
        agreement = SimpleNamespace(status="ready_for_signing")
        with pytest.raises(ValueError, match="15 MB"):
            store_signed_pdf(agreement, upload, uploader_id=1)



def test_production_startup_requires_explicit_private_upload_folder(monkeypatch):
    monkeypatch.setenv("FLASK_ENV", "production")
    monkeypatch.setenv("SECRET_KEY", "x" * 48)
    monkeypatch.setenv("DATABASE_URL", "postgresql://unused:unused@127.0.0.1/unused")
    monkeypatch.delenv("PRIVATE_UPLOAD_FOLDER", raising=False)
    from app import create_app

    with pytest.raises(RuntimeError, match="PRIVATE_UPLOAD_FOLDER"):
        create_app()


@pytest.mark.parametrize("account_type", ["student", "professional", "family", "individual"])
def test_all_accommodation_seeker_categories_register_into_compatible_renter_workflow(app, account_type):
    from app.models import User, db

    client = app.test_client()
    response = client.post("/register", data={
        "role": account_type,
        "name": f"Test {account_type.title()}",
        "email": f"{account_type}@marketplace.test",
        "phone": "+263700000000",
        "password": "test-password-123",
    })
    assert response.status_code == 302
    with app.app_context():
        user = User.query.filter_by(email=f"{account_type}@marketplace.test").one()
        assert user.role == "student"
        assert user.seeker_type == account_type
        assert user.is_approved is True
    dashboard = client.get("/dashboard")
    assert dashboard.status_code == 302
    assert dashboard.location.endswith("/student/dashboard")


def test_legacy_student_registration_remains_supported(app):
    from app.models import User

    response = app.test_client().post("/register", data={
        "role": "student",
        "name": "Legacy Student",
        "email": "legacy-student@marketplace.test",
        "password": "test-password-123",
    })
    assert response.status_code == 302
    with app.app_context():
        user = User.query.filter_by(email="legacy-student@marketplace.test").one()
        assert user.role == "student"
        assert user.seeker_type == "student"


def test_general_marketplace_keyword_and_price_filters(app):
    from app.models import Property, User, db

    with app.app_context():
        landlord = User(
            name="Marketplace Landlord",
            email="marketplace-landlord@test.homebridge",
            password=generate_password_hash("landlord-password-123"),
            role="landlord",
            is_approved=True,
        )
        db.session.add(landlord)
        db.session.flush()
        listing = Property(
            landlord_id=landlord.id,
            title="Avondale family apartment",
            description="Two bedroom apartment close to shops",
            property_type="apartment",
            price=450,
            location="Avondale",
            city="Harare",
            country="Zimbabwe",
            bedrooms=2,
            is_verified=True,
            is_published=True,
            availability_status="available",
        )
        db.session.add(listing)
        db.session.commit()
        listing_id = listing.id

    client = app.test_client()
    matching = client.get("/properties?q=Avondale&min_price=400&max_price=500")
    assert matching.status_code == 200
    assert b"Avondale family apartment" in matching.data

    outside_budget = client.get("/properties?q=Avondale&min_price=500")
    assert outside_budget.status_code == 200
    assert b"Avondale family apartment" not in outside_budget.data

    old_bookmark = client.get("/properties?institution=Avondale")
    assert old_bookmark.status_code == 200
    assert b"Avondale family apartment" in old_bookmark.data

 
def test_general_accommodation_seeker_migration_is_additive():
    migration = Path("migrations/20261127_general_accommodation_seekers.sql").read_text(encoding="utf-8")
    assert 'ADD COLUMN IF NOT EXISTS seeker_type VARCHAR(30)' in migration
    assert "WHERE role = 'student' AND seeker_type IS NULL" in migration
    assert "CREATE INDEX IF NOT EXISTS ix_user_seeker_type" in migration


def test_release_preflight_checks_admin_and_marketplace_schema():
    script = Path("scripts/homebridge_release_preflight.sh").read_text(encoding="utf-8")
    for table in (
        "admin_role", "admin_permission", "admin_role_permission",
        "admin_user_role", "admin_audit_log",
    ):
        assert table in script
    assert '"seeker_type"' in script
    assert '"must_change_password"' in script
