"""Shared rental-agreement workflow helpers.

The generated agreement remains a draft. Review acknowledgements are recorded
separately, and an uploaded signed PDF is stored as a distinct artifact.
"""
from datetime import datetime
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
    uploaded_file.save(destination)
    destination.chmod(0o600)

    agreement.signed_document_path = relative_path
    agreement.signed_uploaded_by_id = uploader_id
    agreement.signed_uploaded_at = datetime.utcnow()
    agreement.status = "signed_copy_uploaded"
    agreement.updated_at = datetime.utcnow()
    db.session.commit()
    return relative_path
