-- HomeBridge administrator RBAC, staff management, and audit trail.
-- Apply after a verified PostgreSQL backup and before deploying the matching app release.
-- Safe to re-run; existing administrator accounts retain their previous full access.

BEGIN;

ALTER TABLE "user"
    ADD COLUMN IF NOT EXISTS must_change_password BOOLEAN NOT NULL DEFAULT FALSE;

CREATE TABLE IF NOT EXISTS admin_role (
    id SERIAL PRIMARY KEY,
    key VARCHAR(40) NOT NULL UNIQUE,
    name VARCHAR(80) NOT NULL,
    description VARCHAR(255) NOT NULL,
    is_system BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS admin_permission (
    id SERIAL PRIMARY KEY,
    key VARCHAR(100) NOT NULL UNIQUE,
    name VARCHAR(120) NOT NULL,
    description VARCHAR(255) NOT NULL
);

CREATE TABLE IF NOT EXISTS admin_role_permission (
    role_id INTEGER NOT NULL REFERENCES admin_role(id) ON DELETE CASCADE,
    permission_id INTEGER NOT NULL REFERENCES admin_permission(id) ON DELETE CASCADE,
    PRIMARY KEY (role_id, permission_id)
);

CREATE TABLE IF NOT EXISTS admin_user_role (
    user_id INTEGER PRIMARY KEY REFERENCES "user"(id) ON DELETE CASCADE,
    role_id INTEGER NOT NULL REFERENCES admin_role(id),
    assigned_by_id INTEGER REFERENCES "user"(id) ON DELETE SET NULL,
    assigned_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_admin_user_role_role_id
    ON admin_user_role(role_id);

CREATE TABLE IF NOT EXISTS admin_audit_log (
    id SERIAL PRIMARY KEY,
    actor_user_id INTEGER REFERENCES "user"(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    target_type VARCHAR(80) NOT NULL,
    target_id VARCHAR(80),
    summary VARCHAR(500) NOT NULL,
    before_state TEXT,
    after_state TEXT,
    ip_address VARCHAR(64),
    user_agent VARCHAR(300),
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_admin_audit_log_actor_user_id ON admin_audit_log(actor_user_id);
CREATE INDEX IF NOT EXISTS ix_admin_audit_log_action ON admin_audit_log(action);
CREATE INDEX IF NOT EXISTS ix_admin_audit_log_target_type ON admin_audit_log(target_type);
CREATE INDEX IF NOT EXISTS ix_admin_audit_log_target_id ON admin_audit_log(target_id);
CREATE INDEX IF NOT EXISTS ix_admin_audit_log_created_at ON admin_audit_log(created_at);

INSERT INTO admin_role (key, name, description, is_system) VALUES
    ('super_admin', 'Super Admin', 'Full platform control, including staff and security administration.', TRUE),
    ('operations', 'Operations', 'User approvals, property moderation, and operational case handling.', TRUE),
    ('finance', 'Finance', 'Platform payment reviews, fee configuration, and financial reporting.', TRUE),
    ('support', 'Support', 'Customer inquiries and support-case handling with limited account visibility.', TRUE),
    ('auditor', 'Auditor', 'Read-only access to operational, financial, staff, and audit information.', TRUE)
ON CONFLICT (key) DO NOTHING;

INSERT INTO admin_permission (key, name, description) VALUES
    ('dashboard.view', 'View administration dashboard', 'View platform operational summary.'),
    ('users.view', 'View user accounts', 'View student and landlord account information.'),
    ('users.approve', 'Approve landlord accounts', 'Approve landlord registration requests.'),
    ('users.suspend', 'Suspend user accounts', 'Deactivate or reactivate user accounts.'),
    ('staff.view', 'View administrator staff', 'View staff accounts and assigned roles.'),
    ('staff.manage', 'Manage administrator staff', 'Create staff accounts, assign roles, and suspend staff.'),
    ('properties.view', 'View property listings', 'View marketplace listings and their moderation state.'),
    ('properties.moderate', 'Moderate properties', 'Verify, reject, publish, unpublish, and feature listings.'),
    ('properties.create', 'Create platform listings', 'Create a listing on behalf of the platform.'),
    ('finance.payments.view', 'View platform payments', 'View platform service-fee and listing-fee payments.'),
    ('finance.payments.review', 'Review platform payments', 'Confirm or reject platform payments.'),
    ('finance.proofs.download', 'Download payment proofs', 'Access private platform-payment proof documents.'),
    ('finance.reports.view', 'View financial reports', 'View platform revenue and payment summaries.'),
    ('finance.settings.manage', 'Manage platform fees', 'Change student service and landlord listing fees.'),
    ('support.cases.view', 'View support inquiries', 'View public inquiries and support cases.'),
    ('support.cases.manage', 'Handle support inquiries', 'Mark inquiries as handled and manage operational support.'),
    ('agreements.view', 'View rental agreements', 'View agreement status and metadata.'),
    ('agreements.documents.download', 'Download signed agreements', 'Access private signed rental-agreement documents.'),
    ('audit.view', 'View audit history', 'Search the administrator audit trail.'),
    ('security.password.change', 'Change own password', 'Change the signed-in administrator password.')
ON CONFLICT (key) DO NOTHING;

-- Super Admin: every defined permission.
INSERT INTO admin_role_permission (role_id, permission_id)
SELECT r.id, p.id
FROM admin_role r CROSS JOIN admin_permission p
WHERE r.key = 'super_admin'
ON CONFLICT DO NOTHING;

-- Operations: user approvals, property moderation, and support operations.
INSERT INTO admin_role_permission (role_id, permission_id)
SELECT r.id, p.id FROM admin_role r JOIN admin_permission p
  ON p.key IN ('dashboard.view','users.view','users.approve','users.suspend',
    'properties.view','properties.moderate','properties.create',
    'support.cases.view','support.cases.manage','agreements.view',
    'agreements.documents.download','security.password.change')
WHERE r.key = 'operations'
ON CONFLICT DO NOTHING;

-- Finance: platform payments, fee settings, revenue, and audit review.
INSERT INTO admin_role_permission (role_id, permission_id)
SELECT r.id, p.id FROM admin_role r JOIN admin_permission p
  ON p.key IN ('dashboard.view','finance.payments.view','finance.payments.review',
    'finance.proofs.download','finance.reports.view','finance.settings.manage',
    'audit.view','security.password.change')
WHERE r.key = 'finance'
ON CONFLICT DO NOTHING;

-- Support: inquiry handling and limited account/agreement visibility.
INSERT INTO admin_role_permission (role_id, permission_id)
SELECT r.id, p.id FROM admin_role r JOIN admin_permission p
  ON p.key IN ('dashboard.view','users.view','support.cases.view',
    'support.cases.manage','agreements.view','security.password.change')
WHERE r.key = 'support'
ON CONFLICT DO NOTHING;

-- Auditor: read-only operational, financial, staff, and audit visibility.
INSERT INTO admin_role_permission (role_id, permission_id)
SELECT r.id, p.id FROM admin_role r JOIN admin_permission p
  ON p.key IN ('dashboard.view','users.view','staff.view','properties.view',
    'finance.payments.view','finance.reports.view','agreements.view',
    'audit.view','security.password.change')
WHERE r.key = 'auditor'
ON CONFLICT DO NOTHING;

-- Every pre-existing unrestricted admin is initially mapped to Super Admin.
-- The Super Admin can then assign the narrower staff roles from the staff console.
INSERT INTO admin_user_role (user_id, role_id, assigned_by_id, assigned_at)
SELECT u.id, r.id, NULL, CURRENT_TIMESTAMP
FROM "user" u CROSS JOIN admin_role r
WHERE u.role = 'admin'
  AND r.key = 'super_admin'
  AND NOT EXISTS (
      SELECT 1 FROM admin_user_role aur WHERE aur.user_id = u.id
  )
ON CONFLICT (user_id) DO NOTHING;

COMMIT;
