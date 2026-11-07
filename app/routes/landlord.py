from functools import wraps
from datetime import datetime
from zoneinfo import ZoneInfo
import os
from uuid import uuid4

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app.models import Application, MaintenanceRequest, Payment, PlatformSetting, Property, PropertyImage, PropertyLocalDetails, RentPayment, Tenancy, TenancyOffer, ViewingAppointment, db

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
    from app.media_uploads import store_property_image
    return store_property_image(file)


def save_payment_proof(file):
    from app.private_uploads import store_platform_payment_proof
    return store_platform_payment_proof(file)


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


def save_local_details(prop):
    institution = request.form.get("institution_name", "").strip() or None
    campus = request.form.get("campus_name", "").strip() or None
    raw_distance = request.form.get("distance_km", "").strip()
    try:
        distance = float(raw_distance) if raw_distance else None
    except ValueError:
        distance = None

    currency = request.form.get("rent_currency", "USD").strip().upper()
    currency_map = {"USD": "USD", "ZIG": "ZiG", "ZAR": "ZAR"}
    rent_currency = currency_map.get(currency, "USD")
    period = request.form.get("rent_period", "month").strip().lower()
    rent_period = period if period in {"month", "week", "term"} else "month"

    has_local_details = bool(institution or campus or distance is not None or rent_currency != "USD" or rent_period != "month")
    if not has_local_details:
        if prop.local_details:
            db.session.delete(prop.local_details)
        return

    details = prop.local_details
    if details is None:
        details = PropertyLocalDetails(property=prop)
        db.session.add(details)
    details.institution_name = institution
    details.campus_name = campus
    details.distance_km = distance
    details.rent_currency = rent_currency
    details.rent_period = rent_period


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
    applications = Application.query.join(Property).filter(Property.landlord_id == current_user.id).order_by(Application.submitted_at.desc()).limit(10).all() if property_ids else []
    maintenance = MaintenanceRequest.query.filter(MaintenanceRequest.property_id.in_(property_ids)).order_by(MaintenanceRequest.reported_at.desc()).limit(10).all() if property_ids else []
    rent_payments = RentPayment.query.filter(RentPayment.property_id.in_(property_ids)).order_by(RentPayment.submitted_at.desc()).limit(10).all() if property_ids else []
    platform_payments = Payment.query.filter_by(user_id=current_user.id).order_by(Payment.submitted_at.desc()).limit(10).all()
    tenancies = Tenancy.query.join(Property).filter(Property.landlord_id == current_user.id).order_by(Tenancy.created_at.desc()).limit(20).all()
    return render_template("landlord/dashboard.html", properties=properties, applications=applications, maintenance=maintenance, rent_payments=rent_payments, platform_payments=platform_payments, tenancies=tenancies, listing_fee=listing_fee(), listing_fee_paid=has_confirmed_listing_fee())


@landlord.route("/applications/<int:application_id>")
@landlord_required
def application_detail(application_id):
    application = Application.query.join(Property).filter(
        Application.id == application_id,
        Property.landlord_id == current_user.id
    ).first_or_404()
    return render_template("landlord/application_detail.html", application=application)


@landlord.route("/applications/<int:application_id>/decision", methods=["POST"])
@landlord_required
def decide_application(application_id):
    application = Application.query.join(Property).filter(
        Application.id == application_id,
        Property.landlord_id == current_user.id
    ).first_or_404()
    decision = request.form.get("decision", "").strip().lower()
    if application.status not in {"pending", "under_review"}:
        flash("This application has already been decided or withdrawn.", "warning")
    elif decision not in {"approved", "rejected", "under_review"}:
        flash("Choose a valid application decision.", "danger")
    else:
        application.status = decision
        db.session.commit()
        flash(f"Application {decision.replace('_', ' ')}.", "success")
    return redirect(url_for("landlord.application_detail", application_id=application.id))


@landlord.route("/applications/<int:application_id>/viewing", methods=["POST"])
@landlord_required
def propose_viewing(application_id):
    application = Application.query.join(Property).filter(
        Application.id == application_id,
        Property.landlord_id == current_user.id
    ).first_or_404()
    if application.status != "approved":
        flash("A viewing can only be arranged after accepting the application.", "warning")
        return redirect(url_for("landlord.application_detail", application_id=application.id))

    raw_datetime = request.form.get("scheduled_at", "").strip()
    meeting_details = request.form.get("meeting_details", "").strip()
    try:
        scheduled_at = datetime.strptime(raw_datetime, "%Y-%m-%dT%H:%M")
    except ValueError:
        scheduled_at = None
    if not scheduled_at or scheduled_at <= datetime.now(ZoneInfo("Africa/Harare")).replace(tzinfo=None):
        flash("Choose a valid future viewing date and time.", "danger")
    elif not meeting_details:
        flash("Add meeting details, such as the property address or a safe meeting point.", "danger")
    else:
        appointment = ViewingAppointment.query.filter_by(application_id=application.id).first()
        if appointment and appointment.status == "confirmed":
            flash("This viewing is already confirmed. Cancel it before proposing another time.", "warning")
        else:
            if appointment is None:
                appointment = ViewingAppointment(application_id=application.id, proposed_by_id=current_user.id)
                db.session.add(appointment)
            appointment.proposed_by_id = current_user.id
            appointment.scheduled_at = scheduled_at
            appointment.meeting_details = meeting_details
            appointment.status = "proposed"
            db.session.commit()
            flash("Viewing proposal saved. The student can respond from My Applications.", "success")
    return redirect(url_for("landlord.application_detail", application_id=application.id))


@landlord.route("/applications/<int:application_id>/viewing/cancel", methods=["POST"])
@landlord_required
def cancel_viewing(application_id):
    application = Application.query.join(Property).filter(
        Application.id == application_id,
        Property.landlord_id == current_user.id
    ).first_or_404()
    appointment = ViewingAppointment.query.filter_by(application_id=application.id).first_or_404()
    if appointment.status in {"proposed", "confirmed"}:
        appointment.status = "cancelled"
        db.session.commit()
        flash("Viewing cancelled.", "success")
    return redirect(url_for("landlord.application_detail", application_id=application.id))



@landlord.route("/tenancies")
@landlord_required
def tenancies():
    items = Tenancy.query.join(Property).filter(Property.landlord_id == current_user.id).order_by(Tenancy.created_at.desc()).all()
    offers = TenancyOffer.query.join(Application).join(Property).filter(Property.landlord_id == current_user.id).order_by(TenancyOffer.created_at.desc()).all()
    return render_template("landlord/tenancies.html", tenancies=items, offers=offers)


@landlord.route("/applications/<int:application_id>/tenancy-offer", methods=["POST"])
@landlord_required
def propose_tenancy_offer(application_id):
    from decimal import Decimal, InvalidOperation
    application = Application.query.join(Property).filter(Application.id == application_id, Property.landlord_id == current_user.id).first_or_404()
    if application.status != "approved":
        flash("A tenancy offer can only be made for an approved application.", "warning")
        return redirect(url_for("landlord.application_detail", application_id=application.id))
    viewing = ViewingAppointment.query.filter_by(application_id=application.id).first()
    if not viewing or viewing.status != "confirmed":
        flash("The student must confirm a viewing before you can make a tenancy offer.", "warning")
        return redirect(url_for("landlord.application_detail", application_id=application.id))
    if Tenancy.query.filter_by(application_id=application.id).first():
        flash("A tenancy already exists for this application.", "warning")
        return redirect(url_for("landlord.application_detail", application_id=application.id))
    try:
        amount = Decimal(request.form.get("rent_amount", "").strip())
        if not amount.is_finite() or amount <= 0 or amount > Decimal("9999999999.99"):
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        flash("Enter a valid rent amount greater than zero.", "danger")
        return redirect(url_for("landlord.application_detail", application_id=application.id))
    currency = {"USD":"USD", "ZIG":"ZiG", "ZAR":"ZAR"}.get(request.form.get("rent_currency", "USD").strip().upper())
    period = request.form.get("rent_period", "month").strip().lower()
    if not currency or period not in {"month", "week", "term"}:
        flash("Choose a supported rent currency and payment period.", "danger")
        return redirect(url_for("landlord.application_detail", application_id=application.id))
    try:
        start_date = datetime.strptime(request.form.get("start_date", ""), "%Y-%m-%d").date()
        raw_end = request.form.get("end_date", "").strip()
        end_date = datetime.strptime(raw_end, "%Y-%m-%d").date() if raw_end else None
    except ValueError:
        flash("Enter valid tenancy dates.", "danger")
        return redirect(url_for("landlord.application_detail", application_id=application.id))
    today = datetime.now(ZoneInfo("Africa/Harare")).date()
    if start_date < today or (end_date and end_date <= start_date):
        flash("The start date must be today or later, and the end date must be after it.", "danger")
        return redirect(url_for("landlord.application_detail", application_id=application.id))
    offer = TenancyOffer.query.filter_by(application_id=application.id).first()
    if offer and offer.status == "proposed":
        flash("An offer is already awaiting the student's response.", "warning")
        return redirect(url_for("landlord.application_detail", application_id=application.id))
    if offer is None:
        offer = TenancyOffer(application_id=application.id, proposed_by_id=current_user.id)
        db.session.add(offer)
    offer.proposed_by_id = current_user.id
    offer.rent_amount, offer.rent_currency, offer.rent_period = amount, currency, period
    offer.room_label = request.form.get("room_label", "").strip()[:100] or None
    offer.start_date, offer.end_date = start_date, end_date
    offer.terms = request.form.get("terms", "").strip()[:4000] or None
    offer.status = "proposed"
    db.session.commit()
    flash("Tenancy offer sent. The student can review it under My Applications.", "success")
    return redirect(url_for("landlord.application_detail", application_id=application.id))

@landlord.route("/payments")
@landlord_required
def payment_history():
    payments = Payment.query.filter_by(user_id=current_user.id).order_by(Payment.submitted_at.desc()).all()
    return render_template("landlord/payments.html", payments=payments)


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
    try:
        proof_file = save_payment_proof(proof) if proof and proof.filename else None
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("landlord.listing_fee_page"))
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
        save_local_details(prop)
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
        save_local_details(prop)
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
    if not current_user.is_approved:
        flash("Your landlord account must be approved before you can submit a property.", "warning")
        return redirect(url_for("landlord.dashboard"))
    if not has_confirmed_listing_fee():
        flash("Your landlord listing fee must be confirmed before submitting a property.", "warning")
        return redirect(url_for("landlord.listing_fee_page"))
    prop.is_verified = False
    prop.is_published = False
    prop.is_featured = False
    db.session.commit()
    flash("Property submitted for admin verification.", "success")
    return redirect(url_for("landlord.properties"))
