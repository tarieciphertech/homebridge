# HomeBridge deployment and release procedure

This document is a release checklist, not authorization to deploy. The current integration branch has not been deployed to the Oracle host.

## Required environment

Set the following outside Git:

- `FLASK_ENV=production`
- `SECRET_KEY`: randomly generated, at least 32 characters
- `DATABASE_URL`: production PostgreSQL connection string
- `ADMIN_EMAIL` and `ADMIN_PASSWORD` for first administrator provisioning only
- `PRIVATE_UPLOAD_FOLDER`: absolute path outside the public web root
- Mail and payment configuration as required by the business

Generate a secret with:

```bash
python -c 'import secrets; print(secrets.token_urlsafe(48))'
```

Do not use the placeholder values in `.env.example` in production.

## Database release procedure

1. Confirm the target database and current schema.
2. Take a PostgreSQL custom-format backup.
3. Verify the backup is readable with `pg_restore --list`.
4. Confirm the baseline application schema exists.
5. Apply `migrations/20261102_tenancy_workflows.sql`.
6. Apply `migrations/20261120_agreements_notifications.sql`.
7. Verify the new columns, tables, indexes and foreign keys.
8. Rehearse the complete migration sequence against a restored copy before production.

The application deliberately does not call `db.create_all()` in production. It is used only for development and disposable CI databases. Do not use it as a production migration tool.

## Private uploads

- Create `PRIVATE_UPLOAD_FOLDER` outside `app/static` and outside any Nginx public alias.
- Set the directory owner to the HomeBridge application user.
- Restrict the directory to mode `0700`; private files are written with mode `0600`.
- Include the private upload directory in encrypted, access-controlled backups.
- Review legacy payment receipts stored under the old `static/uploads/proofs` directory. The Flask static route now blocks those paths, but a direct Nginx alias could bypass Flask. Inspect the actual Nginx configuration and migrate legacy files and database references into private storage before production.
- Verify that anonymous users and ordinary students/landlords cannot download platform payment proofs or signed agreements.

## Application release

1. Confirm both GitHub Actions workflows pass on the exact release commit.
2. Review the pull request and its complete diff.
3. Confirm the database backup and migration rehearsal are successful.
4. Confirm the private upload directory and environment variables are ready.
5. Inspect the existing Compose and Nginx configuration. This Oracle host is shared with other services; do not restart unrelated containers or alter shared host configuration.
6. Deploy only the HomeBridge service using the approved Compose service name and release commit.
7. Check application logs and health endpoints.
8. Test login and role isolation for student, landlord and administrator accounts.
9. Test property image uploads, payment receipt submission/download, agreements, notifications, rent payment review and maintenance reporting.
10. Verify Nginx does not expose private uploads through a static alias.
11. Keep the previous application image and verified database backup available for rollback.

## Go-live gate

Do not onboard paying clients until:

- all automated checks pass;
- role and record-ownership tests pass;
- CSRF protection is confirmed on every POST form;
- database migrations are verified;
- private documents are inaccessible through public routes and direct static hosting;
- student, landlord and administrator journeys pass end to end;
- backup restoration and rollback have been rehearsed;
- the business has approved fee amounts, payment instructions, terms and support procedures.
