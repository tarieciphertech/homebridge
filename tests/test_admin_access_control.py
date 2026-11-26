import importlib
from pathlib import Path

import pytest
from werkzeug.security import check_password_hash, generate_password_hash


@pytest.fixture()
def admin_app(tmp_path, monkeypatch):
    database = tmp_path / "homebridge-admin-test.sqlite"
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{database}")
    monkeypatch.setenv("ADMIN_EMAIL", "root@test.homebridge")
    monkeypatch.setenv("ADMIN_PASSWORD", "test-root-password-123456")
    monkeypatch.setenv("ADMIN_NAME", "Root Administrator")

    import config
    importlib.reload(config)

    from app import create_app
    from app.models import db

    application = create_app()
    application.config.update(TESTING=True, WTF_CSRF_ENABLED=False)
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


def _create_staff(app, role_key, email):
    from app.models import AdminRole, AdminUserRole, User, db

    with app.app_context():
        member = User(
            name=f"{role_key.title()} Staff",
            email=email,
            password=generate_password_hash("staff-password-123456"),
            role="admin",
            is_approved=True,
            is_active_account=True,
        )
        db.session.add(member)
        db.session.flush()
        role = AdminRole.query.filter_by(key=role_key).one()
        db.session.add(AdminUserRole(user_id=member.id, role_id=role.id))
        db.session.commit()
        return member.id


def _login(app, email, password):
    client = app.test_client()
    response = client.post("/login", data={"email": email, "password": password})
    assert response.status_code == 302
    return client


def test_admin_roles_enforce_separation_of_duties(admin_app):
    _create_staff(admin_app, "operations", "operations@test.homebridge")
    _create_staff(admin_app, "finance", "finance@test.homebridge")
    _create_staff(admin_app, "support", "support@test.homebridge")
    _create_staff(admin_app, "auditor", "auditor@test.homebridge")

    operations = _login(admin_app, "operations@test.homebridge", "staff-password-123456")
    assert operations.get("/admin/dashboard").status_code == 200
    assert operations.get("/admin/landlords").status_code == 200
    assert operations.get("/admin/properties").status_code == 200
    assert operations.get("/admin/payments").status_code == 403
    assert operations.get("/admin/settings").status_code == 403
    assert operations.get("/admin/staff").status_code == 403

    finance = _login(admin_app, "finance@test.homebridge", "staff-password-123456")
    assert finance.get("/admin/payments").status_code == 200
    assert finance.get("/admin/revenue").status_code == 200
    assert finance.get("/admin/settings").status_code == 200
    assert finance.get("/admin/properties").status_code == 403
    assert finance.get("/admin/landlords").status_code == 403

    support = _login(admin_app, "support@test.homebridge", "staff-password-123456")
    assert support.get("/admin/inquiries").status_code == 200
    assert support.get("/admin/landlords").status_code == 200
    assert support.get("/admin/payments").status_code == 403
    assert support.get("/admin/audit").status_code == 403

    auditor = _login(admin_app, "auditor@test.homebridge", "staff-password-123456")
    assert auditor.get("/admin/revenue").status_code == 200
    assert auditor.get("/admin/properties").status_code == 200
    assert auditor.get("/admin/staff").status_code == 200
    assert auditor.get("/admin/audit").status_code == 200
    assert auditor.post("/admin/staff/create", data={}).status_code == 403
    assert auditor.post("/admin/confirm-payment/999", data={}).status_code == 403

    super_admin = _login(admin_app, "root@test.homebridge", "test-root-password-123456")
    assert super_admin.get("/admin/staff").status_code == 200
    assert super_admin.get("/admin/audit").status_code == 200


def test_admin_endpoint_permission_map_is_complete(admin_app):
    from app.admin_access import ENDPOINT_PERMISSIONS, ROLE_DEFINITIONS, ROLE_PERMISSION_KEYS

    with admin_app.app_context():
        admin_endpoints = {
            rule.endpoint
            for rule in admin_app.url_map.iter_rules()
            if rule.endpoint.startswith("admin_bp.")
        }
        assert admin_endpoints == set(ENDPOINT_PERMISSIONS)
        assert set(ROLE_DEFINITIONS) == {
            "super_admin", "operations", "finance", "support", "auditor"
        }
        assert set(ROLE_PERMISSION_KEYS) == set(ROLE_DEFINITIONS)
        assert ROLE_PERMISSION_KEYS["auditor"].isdisjoint({
            "staff.manage", "users.approve", "users.suspend",
            "properties.moderate", "finance.payments.review",
            "finance.proofs.download", "finance.settings.manage",
            "support.cases.manage", "agreements.documents.download",
        })


def test_super_admin_can_create_staff_and_first_login_requires_password_change(admin_app):
    from app.models import AdminAuditLog, AdminRole, AdminUserRole, User, db

    root = _login(admin_app, "root@test.homebridge", "test-root-password-123456")
    response = root.post("/admin/staff/create", data={
        "name": "New Support Officer",
        "email": "new-support@test.homebridge",
        "phone": "+263700000000",
        "password": "Temporary-Staff-Password-2026!",
        "role_key": "support",
    })
    assert response.status_code == 302

    with admin_app.app_context():
        member = User.query.filter_by(email="new-support@test.homebridge").one()
        assert member.role == "admin"
        assert member.is_active_account is True
        assert member.must_change_password is True
        assignment = AdminUserRole.query.filter_by(user_id=member.id).one()
        assert assignment.role.key == "support"
        assert AdminAuditLog.query.filter_by(
            action="staff.create", target_id=str(member.id)
        ).count() == 1

    staff_client = _login(
        admin_app,
        "new-support@test.homebridge",
        "Temporary-Staff-Password-2026!",
    )
    assert staff_client.get("/admin/dashboard").status_code == 302
    assert staff_client.get("/admin/force-change-password").status_code == 200

    changed = staff_client.post("/admin/force-change-password", data={
        "current_password": "Temporary-Staff-Password-2026!",
        "new_password": "Personal-Staff-Password-2026-Long!",
        "confirm_password": "Personal-Staff-Password-2026-Long!",
    })
    assert changed.status_code == 302
    assert changed.location.endswith("/admin/dashboard")
    assert staff_client.get("/admin/dashboard").status_code == 200

    with admin_app.app_context():
        member = User.query.filter_by(email="new-support@test.homebridge").one()
        assert member.must_change_password is False
        assert check_password_hash(member.password, "Personal-Staff-Password-2026-Long!")
        assert AdminAuditLog.query.filter_by(
            action="staff.password.initial_change", target_id=str(member.id)
        ).count() == 1


def test_suspending_staff_invalidates_existing_session(admin_app):
    from app.models import User, db

    staff_id = _create_staff(admin_app, "support", "suspended@test.homebridge")
    staff_client = _login(admin_app, "suspended@test.homebridge", "staff-password-123456")
    assert staff_client.get("/admin/inquiries").status_code == 200

    root = _login(admin_app, "root@test.homebridge", "test-root-password-123456")
    response = root.post(f"/admin/staff/{staff_id}/status", data={})
    assert response.status_code == 302

    with admin_app.app_context():
        member = db.session.get(User, staff_id)
        assert member.is_active_account is False
        assert member.is_active is False

    denied = staff_client.get("/admin/inquiries")
    assert denied.status_code == 302
    assert "/login" in denied.location


def test_super_admin_cannot_change_own_role_or_suspend_own_account(admin_app):
    root = _login(admin_app, "root@test.homebridge", "test-root-password-123456")
    with admin_app.app_context():
        from app.models import User
        root_id = User.query.filter_by(email="root@test.homebridge").one().id

    # Self-protection prevents an administrator from removing their own
    # access; another Super Admin is required to manage this account.
    assert root.post(f"/admin/staff/{root_id}/status", data={}).status_code == 302
    assert root.post(f"/admin/staff/{root_id}/role", data={"role_key": "operations"}).status_code == 302

    with admin_app.app_context():
        from app.models import User
        member = User.query.filter_by(email="root@test.homebridge").one()
        assert member.is_active_account is True
        assert member.admin_role_assignments[0].role.key == "super_admin"


def test_audit_migration_is_additive_and_documents_manual_deployment():
    migration = Path("migrations/20261126_admin_access_control.sql").read_text(encoding="utf-8")
    for table in (
        "admin_role", "admin_permission", "admin_role_permission",
        "admin_user_role", "admin_audit_log",
    ):
        assert f"CREATE TABLE IF NOT EXISTS {table}" in migration
    assert 'ALTER TABLE "user"' in migration
    assert "must_change_password" in migration
    assert "WHERE u.role = 'admin'" in migration
    assert "ON CONFLICT" in migration
