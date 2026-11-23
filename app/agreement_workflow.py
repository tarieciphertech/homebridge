"""Shared rental-agreement workflow helpers.

The generated agreement remains a draft. Review acknowledgements are recorded
separately, and an uploaded signed PDF is stored as a distinct artifact.
"""
from datetime import datetime
import json
from pathlib import Path
from uuid import uuid4

from flask import current_app
from werkzeug.utils import secure_filename

from app.models import RentalAgreement, db


def get_or_create_agreement(tenancy):
    agreement = RentalAgreement.query.filter_by(tenancy_id=tenancy.id).first()
    if agreement:
        return agreement

    agreement = RentalAgreement(
        tenancy_id=tenancy.id,
        landlord_id=tenancy.property.landlord_id,
        student_id=tenancy.student_id,
        status="draft",
    )
    db.session.add(agreement)
    db.session.flush()
    return agreement


def record_review(agreement, reviewer_role):
    if agreement.signed_document_path:
        return False
    now = datetime.utcnow()
    if reviewer_role == "landlord":
        agreement.landlord_reviewed_at = now
    elif reviewer_role == "student":
        agreement.student_reviewed_at = now
    else:
        return False

    agreement.status = (
        "ready_for_signing"
        if agreement.landlord_reviewed_at and agreement.student_reviewed_at
        else "under_review"
    )
    agreement.updated_at = now
    db.session.commit()
    return True


def store_signed_pdf(agreement, uploaded_file, uploader_id):
    if not uploaded_file or not uploaded_file.filename:
        raise ValueError("Choose the signed agreement PDF to upload.")
    original_name = secure_filename(uploaded_file.filename)
    if not original_name.lower().endswith(".pdf"):
        raise ValueError("Only PDF documents are accepted.")
    uploaded_file.stream.seek(0, 2)
    size = uploaded_file.stream.tell()
    uploaded_file.stream.seek(0)
    if size <= 0 or size > 15 * 1024 * 1024:
        raise ValueError("The signed agreement PDF must be between 1 byte and 15 MB.")

    header = uploaded_file.stream.read(5)
    uploaded_file.stream.seek(0)
    if header != b"%PDF-":
        raise ValueError("The uploaded file does not appear to be a valid PDF.")
    if agreement.status != "ready_for_signing":
        raise ValueError("Both parties must review the draft before uploading the signed copy.")

    filename = f"agreement-{agreement.id}-{uuid4().hex}.pdf"
    relative_path = str(Path("agreements") / filename)
    folder = Path(current_app.config["PRIVATE_UPLOAD_FOLDER"]) / "agreements"
    folder.mkdir(parents=True, mode=0o700, exist_ok=True)
    folder.chmod(0o700)
    destination = folder / filename
    try:
        uploaded_file.save(destination)
        destination.chmod(0o600)
    except Exception:
        destination.unlink(missing_ok=True)
        raise

    agreement.signed_document_path = relative_path
    agreement.signed_uploaded_by_id = uploader_id
    agreement.signed_uploaded_at = datetime.utcnow()
    agreement.status = "signed_copy_uploaded"
    agreement.updated_at = datetime.utcnow()
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        destination.unlink(missing_ok=True)
        raise
    return relative_path


AGREEMENT_FIELD_LIMITS = {
    "landlord_name": 150, "landlord_email": 120, "landlord_phone": 40,
    "tenant_name": 150, "tenant_email": 120, "tenant_phone": 40,
    "property_title": 200, "room_label": 100, "property_address": 500,
    "property_type": 80, "rent_amount": 30, "rent_currency": 10,
    "rent_period": 20, "payment_due": 120, "payment_method": 180,
    "start_date": 20, "end_date": 20, "deposit": 180,
    "utilities": 1000, "responsibilities": 2000, "notice_period": 500,
    "dispute_resolution": 1000, "additional_terms": 4000,
}


def get_agreement_fields(agreement):
    try:
        saved = json.loads(agreement.editable_fields or "{}")
        if not isinstance(saved, dict):
            saved = {}
    except (TypeError, ValueError):
        saved = {}
    return saved


def save_agreement_fields(agreement, form):
    """Save editable draft text without changing account profiles or signatures."""
    if agreement.signed_document_path:
        raise ValueError("This agreement is locked because a signed copy has been uploaded.")
    values = {}
    for key, limit in AGREEMENT_FIELD_LIMITS.items():
        value = form.get(key, "").strip()
        if len(value) > limit:
            raise ValueError(f"{key.replace('_', ' ').title()} is too long (maximum {limit} characters).")
        values[key] = value
    currency = values["rent_currency"].upper()
    if currency not in {"USD", "ZIG", "ZAR"}:
        raise ValueError("Choose USD, ZiG or ZAR as the rent currency.")
    values["rent_currency"] = {"USD": "USD", "ZIG": "ZiG", "ZAR": "ZAR"}[currency]
    if values["rent_period"].lower() not in {"month", "week", "term"}:
        raise ValueError("Choose month, week or term as the rent period.")
    values["rent_period"] = values["rent_period"].lower()
    if values["rent_amount"]:
        from decimal import Decimal, InvalidOperation
        try:
            amount = Decimal(values["rent_amount"])
            if not amount.is_finite() or amount <= 0 or amount > Decimal("9999999999.99"):
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            raise ValueError("Enter a valid positive rent amount.")
    for key in ("start_date", "end_date"):
        if values[key]:
            try:
                datetime.strptime(values[key], "%Y-%m-%d")
            except ValueError:
                raise ValueError(f"Enter a valid {key.replace('_', ' ')}.")
    if values["start_date"] and values["end_date"] and values["end_date"] <= values["start_date"]:
        raise ValueError("The end date must be after the start date.")
    agreement.editable_fields = json.dumps(values, ensure_ascii=False)
    agreement.landlord_reviewed_at = None
    agreement.student_reviewed_at = None
    agreement.status = "draft"
    agreement.updated_at = datetime.utcnow()
    return values
