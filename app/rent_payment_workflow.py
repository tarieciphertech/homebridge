"""Private proof-of-payment storage for tenant rent submissions."""
from pathlib import Path
from uuid import uuid4

from flask import current_app
from werkzeug.utils import secure_filename


_ALLOWED_SIGNATURES = {
    ".pdf": (b"%PDF-",),
    ".png": (b"\x89PNG\r\n\x1a\n",),
    ".jpg": (b"\xff\xd8\xff",),
    ".jpeg": (b"\xff\xd8\xff",),
}


def store_rent_payment_proof(uploaded_file):
    if not uploaded_file or not uploaded_file.filename:
        raise ValueError("Upload a payment receipt or proof document.")

    safe_name = secure_filename(uploaded_file.filename)
    extension = Path(safe_name).suffix.lower()
    signatures = _ALLOWED_SIGNATURES.get(extension)
    if not signatures:
        raise ValueError("Proof must be a PDF, PNG or JPEG file.")

    uploaded_file.stream.seek(0, 2)
    size = uploaded_file.stream.tell()
    uploaded_file.stream.seek(0)
    if size <= 0 or size > 10 * 1024 * 1024:
        raise ValueError("Proof file must be between 1 byte and 10 MB.")

    header = uploaded_file.stream.read(16)
    uploaded_file.stream.seek(0)
    if not any(header.startswith(signature) for signature in signatures):
        raise ValueError("The uploaded proof does not match its file type.")

    filename = f"rent-proof-{uuid4().hex}{extension}"
    folder = Path(current_app.config["PRIVATE_UPLOAD_FOLDER"]) / "rent-proofs"
    folder.mkdir(parents=True, mode=0o700, exist_ok=True)
    folder.chmod(0o700)
    destination = folder / filename
    uploaded_file.save(destination)
    destination.chmod(0o600)
    return str(Path("rent-proofs") / filename)
