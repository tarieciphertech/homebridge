"""Private storage helpers for sensitive HomeBridge uploads."""
from pathlib import Path
from uuid import uuid4

from flask import current_app
from werkzeug.utils import secure_filename


ALLOWED_PAYMENT_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}


def store_platform_payment_proof(uploaded_file):
    if not uploaded_file or not uploaded_file.filename:
        return None

    original = secure_filename(uploaded_file.filename)
    suffix = Path(original).suffix.lower()
    if not original or suffix not in ALLOWED_PAYMENT_EXTENSIONS:
        raise ValueError("Upload a PDF, PNG, JPG, or WEBP payment receipt.")

    # Verify the file signature instead of trusting the browser-provided MIME type.
    stream = uploaded_file.stream
    header = stream.read(16)
    stream.seek(0)
    signatures = {
        ".pdf": header.startswith(b"%PDF-"),
        ".png": header.startswith(b"\\x89PNG\\r\\n\\x1a\\n"),
        ".jpg": header.startswith(b"\\xff\\xd8\\xff"),
        ".jpeg": header.startswith(b"\\xff\\xd8\\xff"),
        ".webp": len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP",
    }
    if not signatures[suffix]:
        raise ValueError("The uploaded file does not match its file extension.")

    folder = Path(current_app.config["PRIVATE_UPLOAD_FOLDER"]) / "platform-payments"
    folder.mkdir(parents=True, mode=0o700, exist_ok=True)
    folder.chmod(0o700)
    filename = f"payment-{uuid4().hex}{suffix}"
    destination = folder / filename
    uploaded_file.save(destination)
    destination.chmod(0o600)
    return str(Path("platform-payments") / filename)
