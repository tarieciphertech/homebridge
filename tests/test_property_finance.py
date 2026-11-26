from datetime import date
from io import BytesIO
import importlib

import pytest
from werkzeug.security import generate_password_hash


@pytest.fixture()
def app(tmp_path, monkeypatch):
    database = tmp_path / "homebridge-finance-test.sqlite"
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database}")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@finance-test.homebridge")
    monkeypatch.setenv("ADMIN_PASSWORD", "test-admin-password-12345")
    monkeypatch.setenv("ADMIN_NAME", "Test Admin")

    import config
    importlib.reload(config)
    from app import create_app
    from app.models import db

    application = create_app()
    application.config.update(TESTING=True, WTF_CSRF_ENABLED=False, PRIVATE_UPLOAD_FOLDER=str(tmp_path / "private"))
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


def _create_accounts_and_tenancy(app):
    from app.models import Property, Tenancy, User, db

    with app.app_context():
        landlord = User(name="Landlord", email="landlord@finance-test.homebridge", password=generate_password_hash("landlord-password"), role="landlord", is_approved=True)
        tenant = User(name="Tenant", email="tenant@finance-test.homebridge", password=generate_password_hash("tenant-password"), role="student", is_approved=True)
        db.session.add_all([landlord, tenant])
        db.session.flush()
        prop = Property(landlord_id=landlord.id, title="Test Home", description="Test", property_type="house", listing_type="rent", price=500, location="Main Road", city="Gaborone", country="Botswana", is_verified=True, is_published=True)
        db.session.add(prop)
        db.session.flush()
        tenancy = Tenancy(property_id=prop.id, student_id=tenant.id, rent_amount=500, rent_currency="USD", rent_period="month", start_date=date(2026, 1, 1), status="active")
        db.session.add(tenancy)
        db.session.commit()
        return landlord.id, tenant.id, tenancy.id


def _login(client, email, password):
    response = client.post("/login", data={"email": email, "password": password})
    assert response.status_code == 302


def test_tenant_payment_is_visible_to_landlord_and_can_be_confirmed(app):
    from app.models import PropertyCharge, PropertyTransaction

    landlord_id, tenant_id, tenancy_id = _create_accounts_and_tenancy(app)
    landlord_client = app.test_client()
    _login(landlord_client, "landlord@finance-test.homebridge", "landlord-password")
    response = landlord_client.post(f"/landlord/tenancies/{tenancy_id}/charges", data={
        "charge_type": "security_deposit", "title": "Security deposit",
        "amount": "300", "currency": "USD", "due_date": "2026-12-01",
    })
    assert response.status_code == 302

    with app.app_context():
        charge_id = PropertyCharge.query.one().id

    tenant_client = app.test_client()
    _login(tenant_client, "tenant@finance-test.homebridge", "tenant-password")
    response = tenant_client.post(f"/student/charges/{charge_id}/payments", data={
        "amount": "300", "method": "bank_transfer", "reference": "BANK-123",
        "proof_file": (BytesIO(b"%PDF-1.7 test receipt"), "receipt.pdf"),
    }, content_type="multipart/form-data")
    assert response.status_code == 302
    with app.app_context():
        transaction = PropertyTransaction.query.one()
        assert transaction.tenant_id == tenant_id
        assert transaction.landlord_id == landlord_id
        assert transaction.status == "pending"
        transaction_id = transaction.id

    response = landlord_client.get("/landlord/finance")
    assert response.status_code == 200
    assert b"Security deposit" in response.data

    response = landlord_client.post(f"/landlord/transactions/{transaction_id}/review", data={"decision": "confirmed", "review_notes": "Received"})
    assert response.status_code == 302
    with app.app_context():
        charge = PropertyCharge.query.one()
        assert str(charge.paid_amount) == "300.00"
        assert str(charge.balance_due) == "0.00"
        assert PropertyTransaction.query.one().status == "confirmed"

    response = tenant_client.get("/student/finance")
    assert response.status_code == 200
    assert b"Confirmed" in response.data


def test_tenant_cannot_access_another_tenants_charge(app):
    from app.models import PropertyCharge, User, db

    landlord_id, tenant_id, tenancy_id = _create_accounts_and_tenancy(app)
    with app.app_context():
        landlord = db.session.get(User, landlord_id)
        other = User(name="Other tenant", email="other@finance-test.homebridge", password=generate_password_hash("other-password"), role="student", is_approved=True)
        db.session.add(other)
        db.session.flush()
        charge = PropertyCharge(
            tenancy_id=tenancy_id, property_id=landlord.properties[0].id,
            landlord_id=landlord_id, tenant_id=tenant_id, charge_type="rent",
            title="Monthly rent", amount=500, currency="USD", due_date=date(2026, 12, 1),
            created_by_id=landlord_id,
        )
        db.session.add(charge)
        db.session.commit()
        charge_id = charge.id

    other_client = app.test_client()
    _login(other_client, "other@finance-test.homebridge", "other-password")
    assert other_client.get("/student/finance").status_code == 200
    response = other_client.post(f"/student/charges/{charge_id}/payments", data={"amount": "1"})
    assert response.status_code == 404


def test_landlord_cannot_create_charge_for_another_landlords_tenancy(app):
    _, _, tenancy_id = _create_accounts_and_tenancy(app)
    with app.app_context():
        from app.models import User, db
        other_landlord = User(name="Other landlord", email="other-landlord@finance-test.homebridge", password=generate_password_hash("other-password"), role="landlord", is_approved=True)
        db.session.add(other_landlord)
        db.session.commit()

    client = app.test_client()
    _login(client, "other-landlord@finance-test.homebridge", "other-password")
    response = client.post(f"/landlord/tenancies/{tenancy_id}/charges", data={
        "charge_type": "rent", "title": "Rent", "amount": "100",
        "currency": "USD", "due_date": "2026-12-01",
    })
    assert response.status_code == 404
