-- HomeBridge general accommodation seeker profile categories.
-- Additive migration: existing student accounts are retained and labelled as students.
BEGIN;

ALTER TABLE "user"
    ADD COLUMN IF NOT EXISTS seeker_type VARCHAR(30);

UPDATE "user"
SET seeker_type = 'student'
WHERE role = 'student' AND seeker_type IS NULL;

CREATE INDEX IF NOT EXISTS ix_user_seeker_type ON "user"(seeker_type);

COMMIT;
