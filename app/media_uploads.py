"""Validated image storage for public HomeBridge property listings."""
from pathlib import Path
from uuid import uuid4

from flask import current_app
from PIL import Image, UnidentifiedImageError


ALLOWED_IMAGE_FORMATS = {
    "JPEG": ("jpg", "JPEG"),
    "PNG": ("png", "PNG"),
    "WEBP": ("webp", "WEBP"),
}
MAX_IMAGE_PIXELS = 30_000_000


def store_property_image(uploaded_file):
    if not uploaded_file or not uploaded_file.filename:
        return None

    try:
        uploaded_file.stream.seek(0)
        with Image.open(uploaded_file.stream) as image:
            image_format = image.format
            if image_format not in ALLOWED_IMAGE_FORMATS:
                raise ValueError("Property photos must be JPEG, PNG, or WEBP images.")
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise ValueError("The property photo dimensions are too large.")
            image.verify()

        uploaded_file.stream.seek(0)
        with Image.open(uploaded_file.stream) as image:
            image.load()
            extension, output_format = ALLOWED_IMAGE_FORMATS[image.format]
            if output_format == "JPEG":
                image = image.convert("RGB")
            elif output_format == "PNG" and image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGBA")
            elif output_format == "WEBP" and image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGBA")

            folder = Path(current_app.config["UPLOAD_FOLDER"]) / "properties"
            folder.mkdir(parents=True, exist_ok=True)
            filename = f"property-{uuid4().hex}.{extension}"
            destination = folder / filename
            image.save(destination, format=output_format, optimize=True)
            return str(Path("properties") / filename)
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("The uploaded property photo is not a valid image.") from exc
