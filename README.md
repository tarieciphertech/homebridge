# HomeBridge

HomeBridge is a student-focused accommodation marketplace and property-management platform for Zimbabwe.

**Official domain:** `https://homebridge.co.zw`

**Repository:** `tarieciphertech/homebridge`

## Project status

**Current stage: active development / testing**

The core marketplace, user roles, property workflow, payment foundations, and admin controls are implemented. The project is currently being developed and tested on a shared Oracle Cloud development instance.

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

- Create a student account
- Browse published student accommodation
- Filter accommodation by type, city and available rooms
- View property photos, amenities, rules and availability
- Submit and track accommodation applications
- Withdraw pending applications
- Submit student service-fee payment proof when a fee is configured

### Landlords

- Create a landlord account
- Wait for platform approval
- Add and edit accommodation properties
- Upload multiple property photos
- Set rent, rooms, amenities, house rules and availability
- Submit properties for admin verification
- Track verification and publication status
- Submit listing-fee payment proof when a listing fee is configured

### Admins

- Manage students and landlords
- Approve landlord accounts
- Review, verify and reject property submissions
- Publish/unpublish verified properties
- Feature published properties
- Review platform payments and payment proof
- Configure student service and landlord listing fees
- Manage inquiries
- Manage admin settings
- Change the admin password

## Implemented functionality

### Authentication and accounts

- Student registration and login
- Landlord registration and login
- Admin account
- Role-based dashboard redirects
- Account approval checks
- Logout
- Default development admin creation

### Property marketplace

- Public property listing
- Property filtering
- Property detail pages
- Similar-property display
- Landlord property creation and editing
- Property image upload and deletion
- Property submission for verification
- Admin verification, rejection and publication workflow
- Featured-property support
- Availability and room tracking

### Applications

- Students can apply to published properties
- Duplicate active applications are prevented
- Students can view application status
- Pending applications can be withdrawn
- Applications are tied to the student and property

### Payments and fees

The platform supports configurable fees rather than hard-coded business prices:

`Student → Student Service Fee → HomeBridge`

`Landlord → Listing / Management Fee → HomeBridge`

Admin settings currently support:

- Student service fee
- Student service-fee currency
- Landlord listing fee

Payment records support confirmation/rejection workflows and uploaded payment proof.

> **Important development note:** landlord account approval and listing-fee confirmation should remain separate business processes. This is an area to review during the next payment/revenue phase.

## Database

The current PostgreSQL development database contains these application tables:

- `user`
- `property`
- `property_image`
- `application`
- `inquiry`
- `payment`
- `platform_setting`
- `tenancy`
- `rent_payment`
- `maintenance_request`

The application currently uses SQLAlchemy `db.create_all()` for development database initialization. A proper migration system should be introduced before production deployment.

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

The current test deployment lives outside the Git repository at `/opt/homebridge` on the Oracle instance.

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

A `302` response redirecting `/` to `/properties` is expected behavior.

## Important development notes

- Do **not** commit `.env` files, database passwords, mail passwords, API keys, or other secrets.
- The current Oracle database and credentials are for development/testing only.
- Development admin/database credentials must be replaced before production.
- The production deployment should use a proper database migration strategy instead of relying on `db.create_all()`.
- The default admin creation logic currently runs during application startup. The development deployment uses one Gunicorn worker to avoid concurrent default-admin creation. This should be made concurrency-safe before scaling to multiple workers.
- Uploaded property images and payment proofs are stored outside Git-tracked source files.
- The Oracle instance is a shared development/test environment and also hosts other Cypher Technologies services. Changes to Nginx, Docker, PostgreSQL, or firewall configuration must avoid disrupting existing services.

## Next planned development phase

### Phase 3 — Finance and revenue

Planned work includes:

1. Admin revenue dashboard
2. Confirmed-payment revenue calculations
3. Revenue breakdown by fee type
4. Pending, rejected and confirmed payment totals
5. Period filters (today, 7 days, 30 days, all/custom)
6. Student and landlord payment history
7. Payment reference/proof visibility
8. Separate landlord account approval from listing-fee confirmation
9. Optional `confirmed_by` tracking for payments

### Phase 4 — Rental management

Planned work includes:

- Application decision workflow
- Application approval → tenancy creation
- Monthly rent schedules
- Rent payment records
- Rent payment verification
- Student rent history
- Landlord rent history
- Admin rental oversight
- Maintenance workflow improvements

## Team

HomeBridge is being developed by **Tarie Cipher** and **Shelton Moyo**.

Repository access should be limited to authorized project contributors. Never share GitHub passwords, personal access tokens, SSH private keys, or server credentials between team members.

## Legacy repository

The original `tarieciphertech/server-13-53-116-180-edcar` repository is intentionally left unchanged. `tarieciphertech/homebridge` is the active standalone HomeBridge repository.
