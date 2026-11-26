"""Database-backed access control and audit helpers for HomeBridge staff."""

import json
from datetime import datetime
from functools import wraps

from flask import abort, request
from flask_login import current_user

from app.models import (
    AdminAuditLog,
    AdminPermission,
    AdminRole,
    AdminRolePermission,
    AdminUserRole,
    User,
    db,
)

ROLE_DEFINITIONS = {
    "super_admin": ("Super Admin", "Full platform control, including staff and security administration."),
    "operations": ("Operations", "User approvals, property moderation, and operational case handling."),
    "finance": ("Finance", "Platform payment reviews, fee configuration, and financial reporting."),
    "support": ("Support", "Customer inquiries and support-case handling with limited account visibility."),
    "auditor": ("Auditor", "Read-only access to operational, financial, staff, and audit information."),
}

PERMISSION_DEFINITIONS = {
    "dashboard.view": ("View administration dashboard", "View platform operational summary."),
    "users.view": ("View user accounts", "View student and landlord account information."),
    "users.approve": ("Approve landlord accounts", "Approve landlord registration requests."),
    "users.suspend": ("Suspend user accounts", "Deactivate or reactivate user accounts."),
    "staff.view": ("View administrator staff", "View staff accounts and assigned roles."),
    "staff.manage": ("Manage administrator staff", "Create staff accounts, assign roles, and suspend staff."),
    "properties.view": ("View property listings", "View marketplace listings and their moderation state."),
    "properties.moderate": ("Moderate properties", "Verify, reject, publish, unpublish, and feature listings."),
    "properties.create": ("Create platform listings", "Create a listing on behalf of the platform."),
    "finance.payments.view": ("View platform payments", "View platform service-fee and listing-fee payments."),
    "finance.payments.review": ("Review platform payments", "Confirm or reject platform payments."),
    "finance.proofs.download": ("Download payment proofs", "Access private platform-payment proof documents."),
    "finance.reports.view": ("View financial reports", "View platform revenue and payment summaries."),
    "finance.settings.manage": ("Manage platform fees", "Change student service and landlord listing fees."),
    "support.cases.view": ("View support inquiries", "View public inquiries and support cases."),
    "support.cases.manage": ("Handle support inquiries", "Mark inquiries as handled and manage operational support."),
    "agreements.view": ("View rental agreements", "View agreement status and metadata."),
    "agreements.documents.download": ("Download signed agreements", "Access private signed rental-agreement documents."),
    "audit.view": ("View audit history", "Search the administrator audit trail."),
    "security.password.change": ("Change own password", "Change the signed-in administrator's password."),
}

ROLE_PERMISSION_KEYS = {
    "super_admin": set(PERMISSION_DEFINITIONS),
    "operations": {
        "dashboard.view", "users.view", "users.approve", "users.suspend",
        "properties.view", "properties.moderate", "properties.create",
        "support.cases.view", "support.cases.manage", "agreements.view",
        "agreements.documents.download", "security.password.change",
    },
    "finance": {
        "dashboard.view", "finance.payments.view", "finance.payments.review",
        "finance.proofs.download", "finance.reports.view", "finance.settings.manage",
        "audit.view", "security.password.change",
    },
    "support": {
        "dashboard.view", "users.view", "support.cases.view",
        "support.cases.manage", "agreements.view", "security.password.change",
    },
    "auditor": {
        "dashboard.view", "users.view", "staff.view", "properties.view",
        "finance.payments.view", "finance.reports.view", "agreements.view",
        "audit.view", "security.password.change",
    },
}

ENDPOINT_PERMISSIONS = {
    "admin_bp.dashboard": "dashboard.view",
    "admin_bp.agreements": "agreements.view",
    "admin_bp.download_signed_agreement": "agreements.documents.download",
    "admin_bp.settings": "finance.settings.manage",
    "admin_bp.landlords": "users.view",
    "admin_bp.approve_landlord": "users.approve",
    "admin_bp.revenue": "finance.reports.view",
    "admin_bp.payments": "finance.payments.view",
    "admin_bp.payment_proof": "finance.proofs.download",
    "admin_bp.confirm_payment": "finance.payments.review",
    "admin_bp.reject_payment": "finance.payments.review",
    "admin_bp.properties": "properties.view",
    "admin_bp.verify_property": "properties.moderate",
    "admin_bp.reject_property": "properties.moderate",
    "admin_bp.publish_property": "properties.moderate",
    "admin_bp.feature_property": "properties.moderate",
    "admin_bp.add_property": "properties.create",
    "admin_bp.inquiries": "support.cases.view",
    "admin_bp.handle_inquiry": "support.cases.manage",
    "admin_bp.change_password": "security.password.change",
    "admin_bp.staff": "staff.view",
    "admin_bp.create_staff": "staff.manage",
    "admin_bp.change_staff_role": "staff.manage",
    "admin_bp.toggle_staff_status": "staff.manage",
    "admin_bp.audit": "audit.view",
    "admin_bp.force_change_password": "security.password.change",
}


def seed_admin_access_control():
    """Seed the fixed role catalogue for disposable development/CI databases."""
    for key, (name, description) in ROLE_DEFINITIONS.items():
        if not AdminRole.query.filter_by(key=key).first():
            db.session.add(AdminRole(key=key, name=name, description=description, is_system=True))

    for key, (name, description) in PERMISSION_DEFINITIONS.items():
        if not AdminPermission.query.filter_by(key=key).first():
            db.session.add(AdminPermission(key=key, name=name, description=description))

    db.session.flush()
    roles = {role.key: role for role in AdminRole.query.all()}
    permissions = {permission.key: permission for permission in AdminPermission.query.all()}

    for role_key, permission_keys in ROLE_PERMISSION_KEYS.items():
        role = roles[role_key]
        existing = {
            row.permission_id
            for row in AdminRolePermission.query.filter_by(role_id=role.id).all()
        }
        for permission_key in permission_keys:
            permission = permissions[permission_key]
            if permission.id not in existing:
                db.session.add(AdminRolePermission(role_id=role.id, permission_id=permission.id))

    # Legacy admin accounts retain their pre-RBAC unrestricted access during
    # the transition. The production SQL migration performs the same backfill.
    super_admin = roles["super_admin"]
    for user in User.query.filter_by(role="admin").all():
        if not AdminUserRole.query.filter_by(user_id=user.id).first():
            db.session.add(AdminUserRole(user_id=user.id, role_id=super_admin.id))

    db.session.commit()


def validate_admin_access_control():
    """Fail production startup if the reviewed RBAC migration is missing or incomplete."""
    role_rows = {role.key: role for role in AdminRole.query.all()}
    permission_keys = {permission.key for permission in AdminPermission.query.all()}
    missing_roles = set(ROLE_DEFINITIONS) - set(role_rows)
    missing_permissions = set(PERMISSION_DEFINITIONS) - permission_keys
    if missing_roles or missing_permissions:
        raise RuntimeError(
            "Administrator access-control migration is incomplete. "
            f"Missing roles: {sorted(missing_roles)}; "
            f"missing permissions: {sorted(missing_permissions)}."
        )

    for role_key, expected_permissions in ROLE_PERMISSION_KEYS.items():
        role = role_rows[role_key]
        granted = {
            permission.key
            for permission in AdminPermission.query.join(
                AdminRolePermission, AdminRolePermission.permission_id == AdminPermission.id
            ).filter(AdminRolePermission.role_id == role.id).all()
        }
        missing_grants = expected_permissions - granted
        if missing_grants:
            raise RuntimeError(
                f"Administrator role '{role_key}' is missing permissions: {sorted(missing_grants)}."
            )

    assigned_user_ids = db.session.query(AdminUserRole.user_id)
    unassigned_count = User.query.filter(
        User.role == "admin", ~User.id.in_(assigned_user_ids)
    ).count()
    if unassigned_count:
        raise RuntimeError(
            f"{unassigned_count} administrator account(s) have no staff role assignment. "
            "Review the administrator access-control migration before startup."
        )


def assign_admin_role(user, role_key, assigned_by_id=None):
    role = AdminRole.query.filter_by(key=role_key).first()
    if role is None:
        raise ValueError("Choose a valid administrator role.")

    assignment = AdminUserRole.query.filter_by(user_id=user.id).first()
    previous_key = assignment.role.key if assignment and assignment.role else None
    if assignment:
        assignment.role_id = role.id
        assignment.assigned_by_id = assigned_by_id
        assignment.assigned_at = datetime.utcnow()
    else:
        assignment = AdminUserRole(
            user_id=user.id,
            role_id=role.id,
            assigned_by_id=assigned_by_id,
            assigned_at=datetime.utcnow(),
        )
        db.session.add(assignment)
    return previous_key, role_key


def has_admin_permission(user, permission_key):
    if (
        not user
        or not getattr(user, "is_authenticated", False)
        or getattr(user, "role", None) != "admin"
        or not getattr(user, "is_active_account", False)
    ):
        return False

    return db.session.query(AdminPermission.id).join(
        AdminRolePermission, AdminRolePermission.permission_id == AdminPermission.id
    ).join(
        AdminUserRole, AdminUserRole.role_id == AdminRolePermission.role_id
    ).filter(
        AdminUserRole.user_id == user.id,
        AdminPermission.key == permission_key,
    ).first() is not None


def record_admin_audit(action, target_type, target_id=None, summary="", before=None, after=None):
    """Add an audit event to the caller's transaction; never stores credentials."""
    actor_id = current_user.id if current_user.is_authenticated else None
    entry = AdminAuditLog(
        actor_user_id=actor_id,
        action=action[:100],
        target_type=target_type[:80],
        target_id=str(target_id)[:80] if target_id is not None else None,
        summary=summary[:500],
        before_state=json.dumps(before, sort_keys=True, default=str) if before is not None else None,
        after_state=json.dumps(after, sort_keys=True, default=str) if after is not None else None,
        ip_address=(request.remote_addr or "")[:64] or None,
        user_agent=(request.user_agent.string or "")[:300] or None,
    )
    db.session.add(entry)
    return entry


def permission_for_endpoint(endpoint):
    return ENDPOINT_PERMISSIONS.get(endpoint)


def require_endpoint_permission(endpoint):
    permission = permission_for_endpoint(endpoint)
    if not permission or not has_admin_permission(current_user, permission):
        abort(403)
    return True
