# HomeBridge

## Product direction — Zimbabwe-first student accommodation

HomeBridge is being shaped around students and families finding suitable accommodation in Zimbabwe when education takes them away from home. The initial audience includes university, college, polytechnic and secondary-school students, as well as international students studying in Zimbabwe. Parent/guardian involvement should be considered in the experience for younger students.

The marketplace should organize discovery around:
- Zimbabwean cities and education destinations, with initial market focus on Harare, Bulawayo and Gweru.
- Universities, colleges, polytechnics and secondary schools, including the campus or area served.
- Private rooms, shared houses, student lodges, hostels, boarding accommodation, apartments and houses.
- Transparent rent amounts, currencies and payment periods.
- Clear location, campus distance, room availability, amenities, house rules and listing verification.

The first implementation slice adds institution/campus search and landlord listing fields for nearby education institutions, campus/area, distance in kilometres, rent currency (USD, ZiG or ZAR), and rent period (month, week or term). These fields are stored in a separate PropertyLocalDetails table so the existing property table and existing records do not need destructive changes. The app's existing db.create_all() startup creates this new table automatically.

This is a Zimbabwe-first product direction, not a claim that all Zimbabwean institutions or accommodation inventory have already been onboarded. Do not invent listings or imply a property is verified unless an admin has completed the review process.

HomeBridge is a student-focused accommodation marketplace and property-management platform for Zimbabwe.

## Current URLs

| Purpose | URL |
|---|---|
| Main / production domain | https://homebridge.co.zw |
| Current Oracle development/test site | https://homebridge.cyphertech.co.zw |
| Student portal | https://homebridge.co.zw/student |
| Landlord portal | https://homebridge.co.zw/landlord |
| Admin portal | https://homebridge.co.zw/admin |
| Future API | https://api.homebridge.co.zw |
| GitHub repository | https://github.com/tarieciphertech/homebridge |

> **Environment note:** `homebridge.co.zw` is the intended public production domain. The currently deployed and verified development/testing environment is `homebridge.cyphertech.co.zw` on the Oracle instance. The student, landlord, admin, and API URLs above describe the planned/public route structure and should not be assumed to be independently deployed unless verified.

## Latest team handover — 2 November 2026

This section supersedes older status notes where they conflict. It is the latest shared project status for Tariro and Shelton.

### Executive status

**Status:** Development milestone verified.

The latest completed milestone is **tenancy onboarding**. The landlord offer flow, student accept/decline flow, and tenancy dashboards were deployed to the Oracle development environment and confirmed through browser testing by the project team.

### Completed and verified this week

- Landlords can send a tenancy offer only when the student's application is approved and the viewing has been confirmed.
- Offers capture rent amount, currency (USD, ZiG or ZAR), rent period (month, week or term), optional room/unit label, start and end dates, and terms.
- Students can review and accept or decline offers from **My Applications**.
- Accepting an offer creates the HomeBridge tenancy record; declining it does not create a tenancy.
- Student and landlord tenancy pages are available and linked from their dashboards.
- An application-linked unique tenancy reference prevents duplicate tenancy creation.
- The database migration was applied to the `homebridge_dev` database.
- A database backup was taken before the migration.
- The application was updated from GitHub, compiled, rebuilt and restarted on the Oracle development host.
- The landlord offer and student response workflows were tested in the browser and confirmed by the team.

### Technical / deployment notes

- Repository: `tarieciphertech/homebridge`, branch `main`.
- Oracle application directory: `/opt/homebridge/app`.
- Compose file: `/opt/homebridge/docker-compose.yml`.
- Development URL: https://homebridge.cyphertech.co.zw
- Flask application uses SQLAlchemy and PostgreSQL.
- Development database: `homebridge_dev`.
- The app container uses host networking and Gunicorn listens on `127.0.0.1:5001`, behind Nginx.
- Python compilation completed successfully before the container rebuild.
- Unauthenticated HTTP checks for protected tenancy pages returned login redirects as expected; the actual authenticated workflows were separately confirmed in the browser.

**Backups created before the tenancy migration:**
- `/opt/homebridge/backups/homebridge_pre_tenancy_migration_20261102_191843.dump`
- `/opt/homebridge/backups/homebridge_pre_tenancy_migration_20261102_192219.dump`

Keep these backups until the migration and tenancy workflows have had sufficient testing. Never place database credentials, environment variables, SSH keys, or other secrets in this README.

### Important product/legal distinction

A HomeBridge tenancy record stores the details accepted through the platform. It is **not** a signed lease, legal rental contract, proof of rent payment, or confirmation that rent has been collected. The landlord and student must still complete their separate written rental agreement and handle rent payments through their agreed process.

### Next priorities — current work in progress

**Rental agreement lifecycle is under development on `feature/agreement-lifecycle`; it is not merged into `main` or deployed to Oracle.** The current development slice adds:
- Role-protected agreement preview routes for the landlord who owns the tenancy and the student attached to it.
- A per-tenancy `RentalAgreement` workflow record.
- Separate landlord and student review acknowledgements and timestamps.
- Status progression: `draft` → `under_review` → `ready_for_signing` → `signed_copy_uploaded`.
- Signed-PDF upload after both parties have reviewed the draft.
- Private signed-document storage outside the public static directory, with role-checked downloads for the landlord, student, and admin.
- An admin oversight page for agreement status and signed-copy access.
- CI checks for Python compilation, Flask startup, agreement routes, database table creation, and Jinja template loading.

Review acknowledgements are **not electronic signatures**. Uploading a signed PDF does not prove that signatures are genuine or that the agreement is legally valid. HomeBridge does not collect rent or verify payment through this workflow. The draft still requires the parties to complete payment due dates, deposit, utilities, notice, inventory, and any other required terms. Legal wording must be reviewed for the applicable jurisdiction before production use.

Before deployment, complete role-isolation tests, review-state transition tests, PDF upload/download validation, print layout checks, and regression tests for existing tenancy workflows. Confirm private upload directory permissions and backup coverage.

Remaining proposed work:
1. Add notifications when an agreement is ready for review and when the parties complete their offline signing process (if that process is brought into the platform).
2. Test expired offers, repeated submissions, invalid dates, and overlapping tenancy scenarios.
3. Review tenancy status, key dates, rent terms, and contact details.
4. Regression-test application approval, viewing coordination, offer acceptance, and tenancy dashboards.
5. Agree the next weekly priorities and owners.

### Weekly project update agreement

Tariro and Shelton agreed to maintain a **weekly project update** rhythm. Each update should capture:

- What was completed during the week.
- What is deployed and what has been tested, including evidence or outstanding checks.
- Technical decisions, database changes, and backups worth recording.
- Current blockers, risks, and decisions requiring input from either teammate.
- Priorities and ownership for the coming week.

The README should be updated alongside each weekly handover so both contributors have one shared, current record of project progress. The weekly report is a progress record, not a substitute for Git history, deployment verification, or issue tracking.

## Previous handover — 27 October 2026

The following earlier notes are retained as historical context. Where they conflict with the 2 November handover above, use the latest status.

### Verified deployment status at that time

- The Oracle development/test site was reachable over HTTPS: https://homebridge.cyphertech.co.zw/properties
- The public accommodation page rendered HomeBridge navigation, search filters, and the “Student Accommodation” heading.
- The page reported **0 listings** at the time. This can be expected when no properties meet the public listing criteria (published and available); it is not by itself proof that the database or listing route is broken.
- The expected root behavior was a redirect to `/properties`.
- The deployment uses the existing shared Oracle server. Do not rebuild the host or change shared Nginx/PostgreSQL/Docker settings without checking other services first.

### Account display-name issue to investigate

The live page showed **“Lexxi Cipher”** in its visible navigation/account area. This was not confirmed as a code-level issue. Before changing anything, inspect the HomeBridge user table, identify the account and role, confirm the intended development administrator, and preserve access. Do not delete an account or reset credentials without verifying ownership.

### Earlier implementation and roadmap notes

The project has foundations for student/landlord authentication, role-based dashboards, property submissions and image uploads, admin property review/publication, student applications, configurable student service and landlord listing fees, payment-proof submissions, admin payment review, inquiries, and platform settings.

The earlier Phase 3 finance/revenue work included an admin revenue page, date presets and custom date ranges, currency-separated summaries, payment history filters, student/landlord payment history, POST-based confirm/reject actions for pending payments, and separation of landlord account approval from listing-fee confirmation. Continue to verify those workflows on the live development instance before treating them as production-ready.

Finance rules:
- Only platform `Payment` records with `status = confirmed` count as HomeBridge platform revenue.
- Pending and rejected payments are not revenue.
- Rent-payment records belong to the landlord/tenant rental flow and must not be counted as HomeBridge platform-fee revenue unless a separate, explicitly defined business rule is added.
- Do not combine different currencies into a misleading single total.
- Keep landlord account approval separate from confirming a landlord listing-fee payment.

### Zimbabwe-first marketplace rollout

- Validate institution/campus search and local rent terms on the live development deployment.
- Build and maintain a verified directory of Zimbabwean institutions and campuses, starting with Harare, Bulawayo and Gweru.
- Add student profile preferences for institution, campus, budget and intended move-in period.
- Add parent/guardian-assisted inquiry and application support for younger students, with appropriate privacy and safeguarding controls.
- Recruit real landlords and obtain consented property photographs before publishing inventory.

## Project status

**Current stage: active development / testing**

The core marketplace, user roles, property workflow, payment foundations, admin controls, viewing coordination, and tenancy onboarding are implemented to varying degrees. The latest tenancy onboarding slice is deployed and browser-verified in the Oracle development environment. This is not a declaration that the entire platform is production-ready.

### Current development environment

- **Development/test host:** Oracle Cloud VPS
- **Application URL:** `https://homebridge.cyphertech.co.zw`
- **Reverse proxy:** Nginx
- **Application server:** Gunicorn
- **Container:** Docker
- **Application binding:** `127.0.0.1:5001` (not directly Internet-facing)
- **Database:** PostgreSQL 16
- **Development database:** `homebridge_dev`
- **Database binding:** `127.0.0.1:5432` (not publicly exposed)
- **HTTPS:** Enabled with Certbot/Let's Encrypt

The development environment is intentionally separate from the public production domain. Do not treat the Oracle instance as the final production deployment.

## Platform roles

### Students

- Create a student account.
- Browse published student accommodation.
- Filter accommodation by type, city and available rooms.
- View property photos, amenities, rules and availability.
- Submit and track accommodation applications.
- Withdraw pending applications.
- Respond to tenancy offers, view tenancy details, and prepare a printable draft rental agreement for an accepted tenancy (feature branch; not yet deployed).
- Submit student service-fee payment proof when a fee is configured.

### Landlords

- Create a landlord account and wait for platform approval.
- Add and edit accommodation properties.
- Upload multiple property photos.
- Set rent, rooms, amenities, house rules and availability.
- Submit properties for admin verification.
- Track verification and publication status.
- Review applications and coordinate viewings.
- Send tenancy offers for approved applications after viewing confirmation.
- View tenancy details and prepare a printable draft rental agreement for an accepted tenancy (feature branch; not yet deployed).
- Submit listing-fee payment proof when a listing fee is configured.

### Admins

- Manage students and landlords.
- Approve landlord accounts.
- Review, verify and reject property submissions.
- Publish/unpublish verified properties.
- Feature published properties.
- Review platform payments and payment proof.
- Configure student service and landlord listing fees.
- Manage inquiries and admin settings.
- Review platform revenue and payment history.

## Implemented functionality

### Authentication and accounts

- Student registration and login.
- Landlord registration and login.
- Admin account.
- Role-based dashboard redirects.
- Account approval checks.
- Logout.
- Default development admin creation.

### Property marketplace

- Public property listing and filtering.
- Property detail pages and similar-property display.
- Landlord property creation and editing.
- Property image upload and deletion.
- Property submission for verification.
- Admin verification, rejection and publication workflow.
- Featured-property support.
- Availability and room tracking.

### Applications and viewing coordination

- Students can apply to published properties.
- Duplicate active applications are prevented.
- Students can view application status.
- Pending applications can be withdrawn.
- Applications are tied to the student and property.
- Landlords can propose viewing dates/times and meeting instructions after accepting an application.
- Students can confirm or decline proposed viewings from **My Applications**.
- Landlords can cancel proposed or confirmed viewings and issue a replacement proposal.
- Viewing date/time input is interpreted as Zimbabwe local time (Africa/Harare).
- A confirmed viewing does not itself create a tenancy.

### Tenancy onboarding

- Landlords can send tenancy offers for approved applications after viewing confirmation.
- Offers record rent amount, currency (USD, ZiG or ZAR), period (month, week or term), optional room/unit, start/end dates and terms.
- Students can accept or decline offers from **My Applications**.
- Accepting creates a tenancy record; declining does not.
- Student and landlord tenancy pages are linked from their dashboards.
- A printable draft rental agreement preview is available in the feature branch to both parties through role-checked routes; it is not yet merged/deployed and does not capture electronic signatures.
- New tenancy records retain `rent_amount`, `rent_currency` and `rent_period`; legacy `monthly_rent` remains nullable for compatibility and is populated only for monthly offers.
- An application-linked unique tenancy reference prevents duplicate tenancy creation.

The tenancy migration was applied to the development database on 2 November 2026 after database backups were created. Do not repeat the migration blindly. Before any further schema change, inspect the live schema and use a reviewed, backed-up migration.

**Scope boundary:** the current tenancy flow records accepted terms inside HomeBridge. It does not generate a signed lease, collect rent, or prove payment.

### Payments and fees

The platform supports configurable fees rather than hard-coded business prices:

`Student → Student Service Fee → HomeBridge`

`Landlord → Listing / Management Fee → HomeBridge`

Admin settings support student service fee, student service-fee currency, and landlord listing fee. Payment records support confirmation/rejection workflows and uploaded payment proof.

## Database

The PostgreSQL development database contains application tables for users, properties/images, applications, inquiries, platform payments/settings, viewing appointments, tenancies, rent payments, and maintenance requests. Exact schema should be checked against the running database before planning migrations.

The development app has used SQLAlchemy `db.create_all()` for table creation, but this does not alter existing tables to add new columns. The tenancy schema change required a separate migration. Introduce and use a managed migration system consistently before production deployment.

## Technology stack

- Python
- Flask
- Flask-SQLAlchemy
- Flask-Login
- Flask-Mail
- PostgreSQL
- SQLite fallback for local development
- Bootstrap-based responsive UI
- Gunicorn
- Docker
- Nginx
- Certbot / Let's Encrypt

## Repository structure

```text
homebridge/
├── app/
│   ├── routes/
│   │   ├── admin.py
│   │   ├── auth.py
│   │   ├── landlord.py
│   │   ├── public.py
│   │   └── student.py
│   ├── static/
│   │   └── uploads/
│   ├── templates/
│   │   ├── admin/
│   │   ├── auth/
│   │   ├── landlord/
│   │   ├── student/
│   │   └── public/
│   ├── __init__.py
│   ├── models.py
│   └── notifications.py
├── config.py
├── requirements.txt
├── wsgi.py
└── README.md
```

Deployment-specific files such as the Dockerfile, Docker Compose configuration and environment file are maintained on the Oracle development host and should never contain committed secrets.

## Local development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export FLASK_ENV=development
flask --app wsgi:app run
```

For local PostgreSQL development, configure `DATABASE_URL` through the environment rather than committing credentials.

## Oracle development deployment

The current test deployment lives outside the Git repository under `/opt/homebridge` on the Oracle instance.

The application is pulled from the GitHub `main` branch and built with Docker Compose. The production-style container uses Gunicorn and binds only to localhost:

```text
Internet
   ↓
homebridge.cyphertech.co.zw
   ↓
Nginx :443
   ↓
127.0.0.1:5001
   ↓
HomeBridge Docker container
   ↓
PostgreSQL :5432
```

PostgreSQL and Gunicorn are not directly exposed to the public Internet.

### Updating the development server

After a tested change is pushed to `main`, the Oracle development instance can be updated with:

```bash
cd /opt/homebridge/app
git pull origin main
cd /opt/homebridge
docker compose up -d --build
```

Check the application after deployment:

```bash
curl -I https://homebridge.cyphertech.co.zw/
```

A `302` response redirecting `/` to `/properties` is expected behavior. For authenticated features, verify the workflow in a browser using the appropriate role; an unauthenticated redirect is not proof that the feature itself works.

## Important development and security notes

- Do **not** commit `.env` files, database passwords, mail passwords, API keys, or other secrets.
- The current Oracle database and credentials are for development/testing only.
- Development admin/database credentials must be replaced before production.
- Use reviewed, backed-up database migrations for changes to existing tables. A container rebuild does not perform schema migrations automatically.
- The default admin creation logic has previously run during application startup. Review it for concurrency safety before scaling to multiple workers.
- Uploaded property images and payment proofs are stored outside Git-tracked source files.
- The Oracle instance is a shared development/test environment and also hosts other Cypher Technologies services. Changes to Nginx, Docker, PostgreSQL, or firewall configuration must avoid disrupting existing services.
- Do not publish server IPs, private keys, credentials, tokens, or database connection strings in public project documentation.

## Team and collaboration

HomeBridge is being developed by **Tariro Mtshakatshi (Tarie Cipher)** and **Shelton Moyo**.

The team has agreed to maintain weekly progress updates. Keep this README current after each weekly handover, recording completed work, verification status, important technical decisions, blockers, and next priorities. Repository access should be limited to authorized project contributors. Never share GitHub passwords, personal access tokens, SSH private keys, or server credentials.

## Legacy repository

The original `tarieciphertech/server-13-53-116-180-edcar` repository is intentionally left unchanged. `tarieciphertech/homebridge` is the active standalone HomeBridge repository.
