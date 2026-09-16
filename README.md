# Lexxi Cipher Property Management

Standalone property-management project extracted from the property-management functionality in `tarieciphertech/server-13-53-116-180-edcar`.

## Included
- Public property listings with sale/rent/lease filters
- Property detail pages and image galleries
- Property inquiries
- Agent registration and login
- Listing-fee payment proof workflow
- Agent dashboard and property submission
- Admin dashboard
- Admin property publishing/featuring
- Admin payment confirmation and agent activation
- Admin inquiry management
- Configurable Flask/SQLAlchemy/PostgreSQL deployment

## Development

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export FLASK_ENV=development
flask --app wsgi:app run
```

For production, set `DATABASE_URL`, `SECRET_KEY`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`, and mail settings in the environment.

The original `server-13-53-116-180-edcar` repository is intentionally left unchanged; this repository is now the working home for the property-management application.
