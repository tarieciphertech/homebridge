# HomeBridge database migrations

Production schema changes are applied manually and in order after a verified database backup.

1. Take a PostgreSQL backup and confirm that it can be read.
2. Review the SQL against the current production schema.
3. Apply `20261102_tenancy_workflows.sql`.
4. Apply `20261120_agreements_notifications.sql`.
5. Verify the added columns, tables, indexes and foreign keys.
6. Deploy the matching application release only after schema verification.

The Flask application intentionally does not run `db.create_all()` in production. Local development and CI may use it to build disposable test databases. Never use the development database as a substitute for a production migration rehearsal.

The migrations are designed to be repeatable, but they must still be tested against a restored copy of the target database before production use.
