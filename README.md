# HomeBridge

HomeBridge is a student-focused accommodation marketplace and property-management platform for Zimbabwe.

Official domain: `homebridge.co.zw`

## Current platform

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

### Admins
- Manage students and landlords
- Approve landlord accounts
- Review, verify and reject property submissions
- Publish/unpublish verified properties
- Feature published properties
- Review platform payments and payment proof
- Configure student service and landlord listing fees
- Manage inquiries

## Business model foundation

`Student → Student Service Fee → HomeBridge`

`Landlord → Listing / Management Fee → HomeBridge`

Fees are configurable through the admin business settings rather than hard-coded into the application.

## Technology

- Flask
- Flask-SQLAlchemy
- Flask-Login
- Flask-Mail
- PostgreSQL or SQLite for development
- Bootstrap-based responsive UI
- Gunicorn for production

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export FLASK_ENV=development
flask --app wsgi:app run
```

For production, configure `DATABASE_URL`, `SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, and mail settings through environment variables.

The original `tarieciphertech/server-13-53-116-180-edcar` repository is intentionally left unchanged. HomeBridge is the active standalone project repository.
