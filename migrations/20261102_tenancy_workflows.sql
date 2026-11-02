-- HomeBridge tenancy workflow additions (PostgreSQL)
-- Apply only after taking a database backup. Safe to re-run.
BEGIN;

ALTER TABLE maintenance_request
    ADD COLUMN IF NOT EXISTS cost_currency VARCHAR(10) NOT NULL DEFAULT 'USD';

ALTER TABLE rent_payment
    ADD COLUMN IF NOT EXISTS reviewed_by_id INTEGER REFERENCES "user"(id);

ALTER TABLE rent_payment
    ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP WITHOUT TIME ZONE;

ALTER TABLE rent_payment
    ADD COLUMN IF NOT EXISTS review_notes TEXT;

ALTER TABLE rent_payment
    ADD COLUMN IF NOT EXISTS period_start DATE;

ALTER TABLE rent_payment
    ADD COLUMN IF NOT EXISTS period_end DATE;

COMMIT;

-- The new rental_agreement and notification tables are created by the
-- application's existing SQLAlchemy db.create_all() startup step.
