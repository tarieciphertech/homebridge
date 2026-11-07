from io import BytesIO
import os
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

    from app import create_app
    from app.models import db

    application = create_app()
    application.config.update(
        TESTING=True,
        UPLOAD_FOLDER=str(tmp_path / "public"),
        PRIVATE_UPLOAD_FOLDER=str(tmp_path / "private"),
    )
    with application.app_context():
        yield application
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
    response = app.test_client().get("/uploads/proofs/legacy-receipt.pdf")
    assert response.status_code == 404


def test_only_admin_can_download_platform_payment_proof(app):
    from app.models import Payment, db

    with app.app_context():
        private_root = Path(app.config["PRIVATE_UPLOAD_FOLDER"]) / "platform-payments"
        private_root.mkdir(parents=True)
        (private_root / "payment-test.pdf").write_bytes(b"%PDF-1.7 private receipt")
        payment_id = _add_payment(app, "platform-payments/payment-test.pdf")

    anonymous = app.test_client()
    assert anonymous.get(f"/admin/payments/{payment_id}/proof").status_code == 302

    student = app.test_client()
    student.post("/login", data={
        "email": "student@test.homebridge",
        "password": "student-password-123",
    }, follow_redirects=True)
    assert student.get(f"/admin/payments/{payment_id}/proof").status_code == 302

    admin = app.test_client()
    admin.post("/login", data={
        "email": "admin@test.homebridge",
        "password": "test-admin-password-12345",
    }, follow_redirects=True)
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
