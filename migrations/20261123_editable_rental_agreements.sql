-- Persist editable, tenancy-specific rental agreement fields.
-- Apply after taking a verified database backup. Safe to re-run.
BEGIN;
ALTER TABLE rental_agreement ADD COLUMN IF NOT EXISTS editable_fields TEXT;
COMMIT;
