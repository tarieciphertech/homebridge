from functools import wraps
import os
from uuid import uuid4

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app.models import Application, MaintenanceRequest, Payment, PlatformSetting, Property, PropertyImage, RentPayment, db

landlord = Blueprint("landlord", __name__, url_prefix="/landlord")


def landlord_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.role != "landlord":
            return redirect(url_for("auth.dashboard"))
        return view(*args, **kwargs)
    return wrapped


def setting_value(key, default=""):
    setting = PlatformSetting.query.filter_by(key=key).first()
    return setting.value if setting else default


def listing_fee():
    try:
        return float(setting_value("landlord_listing_fee", str(current_app.config.get("LISTING_FEE", 0))))
    except (TypeError, ValueError):
        return 0.0


def has_confirmed_listing_fee():
    fee = listing_fee()
    if fee <= 0:
        return True
    return Payment.query.filter_by(user_id=current_user.id, payment_type="landlord_listing_fee", status="confirmed").first() is not None


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


def save_payment_proof(file):
    filename = secure_filename(file.filename)
    if not filename:
        return None
    folder = os.path.join(current_app.config["UPLOAD_FOLDER"], "proofs")
    os.makedirs(folder, exist_ok=True)
    stem, extension = os.path.splitext(filename)
    final_name = f"{stem}-{uuid4().hex[:10]}{extension.lower()}"
    file.save(os.path.join(folder, final_name))
    return os.path.join("proofs", final_name)


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
    properties = Property.query.filter_by(landlord_id=current_user.id).order_by(Property.submitted_at.desc()).all()
    property_ids = [property.id for property in properties]
    applications = Application.query.filter(Application.property_id.in_(property_ids)).order_by(Application.submitted_at.desc()).limit(10).all() if property_ids else []
    maintenance = MaintenanceRequest.query.filter(MaintenanceRequest.property_id.in_(property_ids)).order_by(MaintenanceRequest.reported_at.desc()).limit(10).all() if property_ids else []
    rent_payments = RentPayment.query.filter(RentPayment.property_id.in_(property_ids)).order_by(RentPayment.submitted_at.desc()).limit(10).all() if property_ids else []
    platform_payments = Payment.query.filter_by(user_id=current_user.id).order_by(Payment.submitted_at.desc()).limit(10).all()
    return render_template("landlord/dashboard.html", properties=properties, applications=applications, maintenance=maintenance, rent_payments=rent_payments, platform_payments=platform_payments, listing_fee=listing_fee(), listing_fee_paid=has_confirmed_listing_fee())


@landlord.route("/listing-fee")
@landlord_required
def listing_fee_page():
    fee = listing_fee()
    currency = setting_value("student_service_fee_currency", "USD")
    pending = Payment.query.filter_by(user_id=current_user.id, payment_type="landlord_listing_fee", status="pending").order_by(Payment.submitted_at.desc()).first()
    return render_template("landlord/listing_fee.html", fee=fee, currency=currency, pending_payment=pending, confirmed=has_confirmed_listing_fee(), payment_details=current_app.config.get("PAYMENT_DETAILS", ""))


@landlord.route("/listing-fee/pay", methods=["POST"])
@landlord_required
def submit_listing_fee():
    fee = listing_fee()
    currency = setting_value("student_service_fee_currency", "USD")
    if fee <= 0:
        flash("No landlord listing fee is currently configured.", "info")
        return redirect(url_for("landlord.listing_fee_page"))
    if has_confirmed_listing_fee():
        flash("Your landlord listing fee is already confirmed.", "success")
        return redirect(url_for("landlord.listing_fee_page"))
    reference = request.form.get("reference", "").strip()
    if not reference:
        flash("Payment reference is required.", "danger")
        return redirect(url_for("landlord.listing_fee_page"))
    if Payment.query.filter_by(reference=reference).first():
        flash("That payment reference has already been submitted.", "warning")
        return redirect(url_for("landlord.listing_fee_page"))
    proof = request.files.get("proof_file")
    proof_file = save_payment_proof(proof) if proof and proof.filename else None
    if not proof_file:
        flash("Please upload proof of payment.", "danger")
        return redirect(url_for("landlord.listing_fee_page"))
    db.session.add(Payment(user_id=current_user.id, payment_type="landlord_listing_fee", amount=fee, currency=currency, reference=reference, proof_file=proof_file, status="pending"))
    db.session.commit()
    flash("Listing-fee payment submitted for admin verification.", "success")
    return redirect(url_for("landlord.listing_fee_page"))


@landlord.route("/properties")
@landlord_required
def properties():
    return render_template("landlord/properties.html", properties=Property.query.filter_by(landlord_id=current_user.id).order_by(Property.submitted_at.desc()).all())


@landlord.route("/properties/new", methods=["GET", "POST"])
@landlord_required
def new_property():
    if not current_user.is_approved:
        flash("Your landlord account must be approved before you can submit a property.", "warning")
        return redirect(url_for("landlord.dashboard"))
    if not has_confirmed_listing_fee():
        flash("Please complete your landlord listing fee before submitting a property.", "warning")
        return redirect(url_for("landlord.listing_fee_page"))
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
    image = PropertyImage.query.join(Property).filter(Property.id == property_id, Property.landlord_id == current_user.id, PropertyImage.id == image_id).first_or_404()
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
    if not has_confirmed_listing_fee():
        flash("Your landlord listing fee must be confirmed before submitting a property.", "warning")
        return redirect(url_for("landlord.listing_fee_page"))
    prop.is_verified = False
    prop.is_published = False
    prop.is_featured = False
    db.session.commit()
    flash("Property submitted for admin verification.", "success")
    return redirect(url_for("landlord.properties"))
