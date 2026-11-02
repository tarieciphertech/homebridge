from functools import wraps
from datetime import datetime
from zoneinfo import ZoneInfo
import os
from uuid import uuid4

from flask import Blueprint, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app.agreement_workflow import get_or_create_agreement, record_review, store_signed_pdf
from app.notifications import create_in_app_notification
from app.models import Application, MaintenanceRequest, Payment, PlatformSetting, Property, PropertyImage, PropertyLocalDetails, RentPayment, Tenancy, TenancyOffer, ViewingAppointment, RentalAgreement, db

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
        create_in_app_notification(
            application.student_id,
            "application_status",
            "Application update",
            f"Your application for {application.property.title} is now {decision.replace('_', ' ')}.",
            url_for("student.applications"),
            current_user.id,
        )
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
            create_in_app_notification(
                application.student_id,
                "viewing_proposed",
                "Viewing proposed",
                f"A viewing for {application.property.title} has been proposed for {scheduled_at.strftime('%d %b %Y at %H:%M')}.",
                url_for("student.applications"),
                current_user.id,
            )
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
        create_in_app_notification(
            application.student_id,
            "viewing_cancelled",
            "Viewing cancelled",
            f"The viewing for {application.property.title} has been cancelled by the landlord.",
            url_for("student.applications"),
            current_user.id,
        )
        db.session.commit()
        flash("Viewing cancelled.", "success")
    return redirect(url_for("landlord.application_detail", application_id=application.id))




@landlord.route("/maintenance")
@landlord_required
def maintenance():
    items = MaintenanceRequest.query.join(Property).filter(
        Property.landlord_id == current_user.id
    ).order_by(MaintenanceRequest.reported_at.desc()).all()
    return render_template("landlord/maintenance.html", requests=items)


@landlord.route("/maintenance/<int:request_id>/update", methods=["POST"])
@landlord_required
def update_maintenance(request_id):
    from decimal import Decimal, InvalidOperation

    item = MaintenanceRequest.query.join(Property).filter(
        MaintenanceRequest.id == request_id,
        Property.landlord_id == current_user.id,
    ).first_or_404()
    status = request.form.get("status", "").strip().lower()
    notes = request.form.get("resolution_notes", "").strip()
    raw_cost = request.form.get("cost", "").strip()
    if status not in {"open", "in_progress", "resolved", "closed"}:
        flash("Choose a valid maintenance status.", "danger")
        return redirect(url_for("landlord.maintenance"))
    try:
        cost = Decimal(raw_cost) if raw_cost else None
        if cost is not None and (not cost.is_finite() or cost < 0 or cost > Decimal("9999999999.99")):
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        flash("Enter a valid non-negative maintenance cost.", "danger")
        return redirect(url_for("landlord.maintenance"))

    item.status = status
    item.resolution_notes = notes[:5000] or None
    item.cost = cost
    item.resolved_at = datetime.utcnow() if status in {"resolved", "closed"} else None
    create_in_app_notification(
        item.reported_by_id,
        "maintenance_updated",
        "Maintenance request updated",
        f"The landlord updated '{item.title}' to {status.replace('_', ' ')}.",
        url_for("student.maintenance"),
        current_user.id,
    )
    db.session.commit()
    flash("Maintenance request updated.", "success")
    return redirect(url_for("landlord.maintenance"))


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
    create_in_app_notification(
        application.student_id,
        "tenancy_offer",
        "New tenancy offer",
        f"{current_user.name} sent you a tenancy offer for {application.property.title}. Review the terms in My Applications.",
        url_for("student.applications"),
        current_user.id,
    )
    db.session.commit()
    flash("Tenancy offer sent. The student can review it under My Applications.", "success")
    return redirect(url_for("landlord.application_detail", application_id=application.id))

@landlord.route("/tenancies/<int:tenancy_id>/agreement")
@landlord_required
def rental_agreement(tenancy_id):
    tenancy = Tenancy.query.join(Property).filter(
        Tenancy.id == tenancy_id,
        Property.landlord_id == current_user.id
    ).first_or_404()
    offer = TenancyOffer.query.filter_by(application_id=tenancy.application_id, status="accepted").first()
    if not offer:
        flash("The accepted offer details for this tenancy could not be found.", "warning")
        return redirect(url_for("landlord.tenancies"))
    agreement = get_or_create_agreement(tenancy)
    if not agreement.prepared_at:
        agreement.prepared_at = datetime.utcnow()
        db.session.commit()
    return render_template(
        "rental_agreement.html",
        tenancy=tenancy,
        offer=offer,
        agreement=agreement,
        generated_at=datetime.utcnow(),
        document_ref=f"HB-TEN-{tenancy.id:06d}",
        back_url=url_for("landlord.tenancies"),
    )



@landlord.route("/tenancies/<int:tenancy_id>/agreement/review", methods=["POST"])
@landlord_required
def review_rental_agreement(tenancy_id):
    tenancy = Tenancy.query.join(Property).filter(
        Tenancy.id == tenancy_id,
        Property.landlord_id == current_user.id
    ).first_or_404()
    agreement = RentalAgreement.query.filter_by(tenancy_id=tenancy.id).first_or_404()
    if not record_review(agreement, "landlord"):
        flash("The signed agreement copy has already been uploaded; review is locked.", "warning")
    else:
        flash("Your agreement review has been recorded.", "success")
    return redirect(url_for("landlord.rental_agreement", tenancy_id=tenancy.id))


@landlord.route("/tenancies/<int:tenancy_id>/agreement/signed-copy", methods=["POST"])
@landlord_required
def upload_signed_rental_agreement(tenancy_id):
    tenancy = Tenancy.query.join(Property).filter(
        Tenancy.id == tenancy_id,
        Property.landlord_id == current_user.id
    ).first_or_404()
    agreement = RentalAgreement.query.filter_by(tenancy_id=tenancy.id).first_or_404()
    try:
        store_signed_pdf(agreement, request.files.get("signed_agreement"), current_user.id)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("landlord.rental_agreement", tenancy_id=tenancy.id))
    flash("Signed PDF uploaded. HomeBridge has stored the document; it has not independently verified signatures or legal validity.", "success")
    return redirect(url_for("landlord.rental_agreement", tenancy_id=tenancy.id))


@landlord.route("/tenancies/<int:tenancy_id>/agreement/signed-copy")
@landlord_required
def download_signed_rental_agreement(tenancy_id):
    tenancy = Tenancy.query.join(Property).filter(
        Tenancy.id == tenancy_id,
        Property.landlord_id == current_user.id
    ).first_or_404()
    agreement = RentalAgreement.query.filter_by(tenancy_id=tenancy.id).first_or_404()
    if not agreement.signed_document_path:
        return redirect(url_for("landlord.rental_agreement", tenancy_id=tenancy.id))
    return send_from_directory(
        current_app.config["PRIVATE_UPLOAD_FOLDER"],
        agreement.signed_document_path,
        as_attachment=True,
        download_name=f"homebridge-signed-agreement-{tenancy.id}.pdf",
    )

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
