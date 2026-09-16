from functools import wraps
import os
from uuid import uuid4

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app.models import Application, MaintenanceRequest, Payment, Property, PropertyImage, RentPayment, db

landlord = Blueprint("landlord", __name__, url_prefix="/landlord")


def landlord_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.role != "landlord":
            return redirect(url_for("auth.dashboard"))
        return view(*args, **kwargs)

    return wrapped


def save_property_image(file):
    original = secure_filename(file.filename)
    if not original:
        return None
    stem, extension = os.path.splitext(original)
    filename = f"{stem}-{uuid4().hex[:10]}{extension.lower()}"
    folder = os.path.join(current_app.config["UPLOAD_FOLDER"], "properties")
    os.makedirs(folder, exist_ok=True)
    file.save(os.path.join(folder, filename))
    return os.path.join("properties", filename)


def property_form_data(prop):
    prop.title = request.form.get("title", "").strip()
    prop.description = request.form.get("description", "").strip()
    prop.property_type = request.form.get("property_type", "house")
    prop.listing_type = request.form.get("listing_type", "rent")
    prop.price = request.form.get("price") or 0
    prop.location = request.form.get("location", "").strip()
    prop.city = request.form.get("city", "").strip()
    prop.country = request.form.get("country", "Zimbabwe").strip() or "Zimbabwe"
    prop.bedrooms = request.form.get("bedrooms") or None
    prop.bathrooms = request.form.get("bathrooms") or None
    prop.available_rooms = request.form.get("available_rooms") or None
    prop.total_rooms = request.form.get("total_rooms") or None
    prop.size_sqm = request.form.get("size_sqm") or None
    prop.amenities = request.form.get("amenities", "").strip()
    prop.house_rules = request.form.get("house_rules", "").strip()
    prop.availability_status = request.form.get("availability_status", "available")


def add_uploaded_images(prop):
    for image in request.files.getlist("images"):
        if image and image.filename:
            filename = save_property_image(image)
            if filename:
                db.session.add(PropertyImage(property_id=prop.id, filename=filename))


@landlord.route("/dashboard")
@landlord_required
def dashboard():
    properties = (
        Property.query.filter_by(landlord_id=current_user.id)
        .order_by(Property.submitted_at.desc())
        .all()
    )
    property_ids = [property.id for property in properties]
    applications = []
    maintenance = []
    rent_payments = []
    if property_ids:
        applications = (
            Application.query.filter(Application.property_id.in_(property_ids))
            .order_by(Application.submitted_at.desc())
            .limit(10)
            .all()
        )
        maintenance = (
            MaintenanceRequest.query.filter(MaintenanceRequest.property_id.in_(property_ids))
            .order_by(MaintenanceRequest.reported_at.desc())
            .limit(10)
            .all()
        )
        rent_payments = (
            RentPayment.query.filter(RentPayment.property_id.in_(property_ids))
            .order_by(RentPayment.submitted_at.desc())
            .limit(10)
            .all()
        )

    platform_payments = (
        Payment.query.filter_by(user_id=current_user.id)
        .order_by(Payment.submitted_at.desc())
        .limit(10)
        .all()
    )
    return render_template(
        "landlord/dashboard.html",
        properties=properties,
        applications=applications,
        maintenance=maintenance,
        rent_payments=rent_payments,
        platform_payments=platform_payments,
    )


@landlord.route("/properties")
@landlord_required
def properties():
    items = Property.query.filter_by(landlord_id=current_user.id).order_by(Property.submitted_at.desc()).all()
    return render_template("landlord/properties.html", properties=items)


@landlord.route("/properties/new", methods=["GET", "POST"])
@landlord_required
def new_property():
    if not current_user.is_approved:
        flash("Your landlord account must be approved before you can submit a property.", "warning")
        return redirect(url_for("landlord.dashboard"))

    if request.method == "POST":
        prop = Property(landlord_id=current_user.id)
        property_form_data(prop)
        if not prop.title or not prop.location or not prop.city or not prop.price:
            flash("Title, location, city and monthly rent are required.", "danger")
            return render_template("landlord/property_form.html", property=prop, mode="create")
        db.session.add(prop)
        db.session.flush()
        add_uploaded_images(prop)
        db.session.commit()
        flash("Property submitted for HomeBridge verification.", "success")
        return redirect(url_for("landlord.properties"))

    return render_template("landlord/property_form.html", property=None, mode="create")


@landlord.route("/properties/<int:property_id>/edit", methods=["GET", "POST"])
@landlord_required
def edit_property(property_id):
    prop = Property.query.filter_by(id=property_id, landlord_id=current_user.id).first_or_404()
    if request.method == "POST":
        property_form_data(prop)
        # Any material landlord edit requires another admin review before publication.
        prop.is_verified = False
        prop.is_published = False
        prop.is_featured = False
        add_uploaded_images(prop)
        db.session.commit()
        flash("Property updated and returned to verification review.", "success")
        return redirect(url_for("landlord.properties"))
    return render_template("landlord/property_form.html", property=prop, mode="edit")


@landlord.route("/properties/<int:property_id>/images/<int:image_id>/delete", methods=["POST"])
@landlord_required
def delete_image(property_id, image_id):
    image = (
        PropertyImage.query.join(Property)
        .filter(Property.id == property_id, Property.landlord_id == current_user.id, PropertyImage.id == image_id)
        .first_or_404()
    )
    image_path = os.path.join(current_app.config["UPLOAD_FOLDER"], image.filename)
    if os.path.exists(image_path):
        os.remove(image_path)
    prop = image.property
    db.session.delete(image)
    prop.is_verified = False
    prop.is_published = False
    prop.is_featured = False
    db.session.commit()
    flash("Image removed. The property has been returned to verification review.", "success")
    return redirect(url_for("landlord.edit_property", property_id=property_id))


@landlord.route("/properties/<int:property_id>/submit", methods=["POST"])
@landlord_required
def submit_property(property_id):
    prop = Property.query.filter_by(id=property_id, landlord_id=current_user.id).first_or_404()
    prop.is_verified = False
    prop.is_published = False
    prop.is_featured = False
    db.session.commit()
    flash("Property submitted for admin verification.", "success")
    return redirect(url_for("landlord.properties"))
