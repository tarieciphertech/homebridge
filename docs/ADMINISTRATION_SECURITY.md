# HomeBridge administrator access control

## Administrator account model

Public account roles remain `student`, `landlord`, and `admin`. Administrator staff accounts continue to use `User.role = 'admin'`; a separate database-backed assignment determines their operational role. This avoids changing student/landlord authorization or existing admin login URLs.

The five fixed staff roles are:

| Role | Scope |
|---|---|
| Super Admin | Full access, including staff administration and security controls |
| Operations | Landlord approvals, property moderation, and operational support |
| Finance | Platform-payment review, private payment proofs, fee settings, and revenue reporting |
| Support | Inquiry handling and limited user/agreement visibility |
| Auditor | Read-only operational, finance, staff, and audit visibility |

Permissions are enforced server-side on every `/admin` endpoint. The navigation only hides links; it is not a security boundary. Unmapped administrator endpoints fail closed with HTTP 403.

## Staff lifecycle

Only a Super Admin can create administrator staff accounts, change their assigned role, or suspend/reactivate them. New staff receive a temporary password of at least 16 characters and must change it before accessing the administration workspace. Suspended accounts are rejected by the user loader, invalidating existing authenticated sessions on their next request.

A staff member cannot change their own role or suspend their own account. The application prevents demoting or suspending the last active Super Admin.

## Audit trail

Privileged staff changes, role changes, status changes, password changes, platform fee changes, landlord approvals, payment decisions, property moderation, inquiry handling, and sensitive document downloads are written to `admin_audit_log` in the same transaction as the relevant change where applicable.

Audit entries record the actor, action, target, timestamp, request IP/user-agent, and safe before/after metadata. Passwords, session tokens, and uploaded document contents are never stored in audit details. Audit history is read-only through the application; database-level tamper resistance still depends on database administration and backup controls.

## Migration and rollout

1. Take and verify a PostgreSQL backup.
2. Apply `migrations/20261126_admin_access_control.sql`.
3. Verify the five role records, permission grants, five RBAC tables, `user.must_change_password`, and the legacy admin assignments.
4. Deploy the matching application release.
5. Sign in with the existing administrator account and open **Staff** to assign narrower roles.

For compatibility, the migration initially maps every pre-existing `role = 'admin'` account to **Super Admin**, preserving its former unrestricted access and avoiding accidental lockout. Review the staff directory after deployment and downgrade any additional administrators to their intended role. Do not remove the final active Super Admin.

The migration is additive. It does not alter student or landlord records, property/payment data, private uploads, or the separate landlord rent-payment workflow. Production startup does not run `db.create_all()`; apply the reviewed SQL migration before deploying the new code.
