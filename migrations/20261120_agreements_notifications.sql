-- HomeBridge agreement, notification, and rent-payment schema additions.
-- Apply after 20261102_tenancy_workflows.sql and after taking a verified backup.
-- Safe to re-run on PostgreSQL.

BEGIN;

ALTER TABLE maintenance_request
    ADD COLUMN IF NOT EXISTS cost_currency VARCHAR(10) NOT NULL DEFAULT 'USD';

ALTER TABLE rent_payment
    ADD COLUMN IF NOT EXISTS period_start DATE;
ALTER TABLE rent_payment
    ADD COLUMN IF NOT EXISTS period_end DATE;
ALTER TABLE rent_payment
    ADD COLUMN IF NOT EXISTS reviewed_by_id INTEGER REFERENCES "user"(id);
ALTER TABLE rent_payment
    ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMP WITHOUT TIME ZONE;
ALTER TABLE rent_payment
    ADD COLUMN IF NOT EXISTS review_notes TEXT;

CREATE TABLE IF NOT EXISTS rental_agreement (
    id SERIAL PRIMARY KEY,
    tenancy_id INTEGER NOT NULL UNIQUE REFERENCES tenancy(id),
    landlord_id INTEGER NOT NULL REFERENCES "user"(id),
    student_id INTEGER NOT NULL REFERENCES "user"(id),
    status VARCHAR(30) NOT NULL DEFAULT 'draft',
    prepared_at TIMESTAMP WITHOUT TIME ZONE,
    landlord_reviewed_at TIMESTAMP WITHOUT TIME ZONE,
    student_reviewed_at TIMESTAMP WITHOUT TIME ZONE,
    signed_document_path VARCHAR(255),
    signed_uploaded_by_id INTEGER REFERENCES "user"(id),
    signed_uploaded_at TIMESTAMP WITHOUT TIME ZONE,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS ix_rental_agreement_landlord_id
    ON rental_agreement (landlord_id);
CREATE INDEX IF NOT EXISTS ix_rental_agreement_student_id
    ON rental_agreement (student_id);
CREATE INDEX IF NOT EXISTS ix_rental_agreement_status
    ON rental_agreement (status);

CREATE TABLE IF NOT EXISTS notification (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES "user"(id),
    actor_id INTEGER REFERENCES "user"(id),
    event_type VARCHAR(50) NOT NULL,
    title VARCHAR(180) NOT NULL,
    message VARCHAR(500) NOT NULL,
    target_url VARCHAR(500),
    is_read BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMP WITHOUT TIME ZONE NOT NULL DEFAULT CURRENT_TIMESTAMP,
    read_at TIMESTAMP WITHOUT TIME ZONE
);

CREATE INDEX IF NOT EXISTS ix_notification_user_id ON notification (user_id);
CREATE INDEX IF NOT EXISTS ix_notification_actor_id ON notification (actor_id);
CREATE INDEX IF NOT EXISTS ix_notification_event_type ON notification (event_type);
CREATE INDEX IF NOT EXISTS ix_notification_is_read ON notification (is_read);
CREATE INDEX IF NOT EXISTS ix_notification_created_at ON notification (created_at);

COMMIT;
