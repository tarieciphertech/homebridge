from functools import wraps
from datetime import datetime
import os
from uuid import uuid4

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app.agreement_workflow import get_or_create_agreement, record_review, store_signed_pdf
from app.notifications import create_in_app_notification\nfrom app.rent_payment_workflow import store_rent_payment_proof
from app.models import Application, MaintenanceRequest, Payment, PlatformSetting, Property, RentPayment, Tenancy, TenancyOffer, ViewingAppointment, RentalAgreement, db

student = Blueprint("student", __name__, url_prefix="/student")


def student_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.role != "student":
            return redirect(url_for("auth.dashboard"))
        return view(*args, **kwargs)
    return wrapped


def get_setting(key, default=""):
    setting = PlatformSetting.query.filter_by(key=key).first()
    return setting.value if setting else default


def student_service_fee():
    try:
        return float(get_setting("student_service_fee", "0"))
    except (TypeError, ValueError):
        return 0.0


def has_confirmed_service_fee():
    fee = student_service_fee()
    if fee <= 0:
        return True
    return Payment.query.filter_by(user_id=current_user.id, payment_type="student_service_fee", status="confirmed").first() is not None


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


@student.route("/dashboard")
@student_required
def dashboard():
    applications = Application.query.filter_by(student_id=current_user.id).order_by(Application.submitted_at.desc()).limit(10).all()
    payments = Payment.query.filter_by(user_id=current_user.id).order_by(Payment.submitted_at.desc()).limit(10).all()
    featured = Property.query.filter_by(is_published=True, availability_status="available").order_by(Property.is_featured.desc(), Property.submitted_at.desc()).limit(6).all()
    tenancies = Tenancy.query.filter_by(student_id=current_user.id).order_by(Tenancy.created_at.desc()).limit(10).all()
    return render_template("student/dashboard.html", applications=applications, payments=payments, featured_properties=featured, tenancies=tenancies, service_fee=student_service_fee(), service_fee_paid=has_confirmed_service_fee())





@student.route("/rent-payments")
@student_required
def rent_payments():
    items = RentPayment.query.filter_by(student_id=current_user.id).order_by(RentPayment.submitted_at.desc()).all()
    tenancies = Tenancy.query.filter_by(student_id=current_user.id, status="active").order_by(Tenancy.created_at.desc()).all()
    return render_template("student/rent_payments.html", rent_payments=items, tenancies=tenancies)


@student.route("/tenancies/<int:tenancy_id>/rent-payments", methods=["POST"])
@student_required
def submit_rent_payment(tenancy_id):
    from decimal import Decimal, InvalidOperation

    tenancy = Tenancy.query.filter_by(id=tenancy_id, student_id=current_user.id, status="active").first_or_404()
    try:
        amount = Decimal(request.form.get("amount", "").strip())
        if not amount.is_finite() or amount <= 0 or amount > Decimal("9999999999.99"):
            raise InvalidOperation
    except (InvalidOperation, ValueError):
        flash("Enter a valid rent amount greater than zero.", "danger")
        return redirect(url_for("student.rent_payments"))

    currency = {"USD": "USD", "ZIG": "ZiG", "ZAR": "ZAR"}.get(request.form.get("currency", "").strip().upper())
    if not currency or currency != tenancy.rent_currency:
        flash(f"Rent payments must use the tenancy currency ({tenancy.rent_currency}).", "danger")
        return redirect(url_for("student.rent_payments"))

    try:
        period_start = datetime.strptime(request.form.get("period_start", ""), "%Y-%m-%d").date()
        period_end = datetime.strptime(request.form.get("period_end", ""), "%Y-%m-%d").date()
        if period_end < period_start:
            raise ValueError
    except ValueError:
        flash("Enter a valid rent coverage period; the end date cannot be before the start date.", "danger")
        return redirect(url_for("student.rent_payments"))
    payment_month = period_start.strftime("%Y-%m")

    existing_payments = RentPayment.query.filter(
        RentPayment.tenancy_id == tenancy.id,
        RentPayment.status.in_(["pending", "confirmed"]),
    ).all()
    for existing in existing_payments:
        if existing.period_start and existing.period_end:
            existing_start, existing_end = existing.period_start, existing.period_end
        else:
            existing_start = datetime.strptime(existing.payment_month + "-01", "%Y-%m-%d").date()
            existing_end = (existing_start.replace(day=28) + __import__("datetime").timedelta(days=4)).replace(day=1) - __import__("datetime").timedelta(days=1)
        if period_start <= existing_end and period_end >= existing_start:
            flash("A pending or confirmed rent payment already covers part of that period.", "warning")
            return redirect(url_for("student.rent_payments"))

    try:
        proof_path = store_rent_payment_proof(request.files.get("proof_file"))
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("student.rent_payments"))

    payment = RentPayment(
        tenancy_id=tenancy.id,
        property_id=tenancy.property_id,
        student_id=current_user.id,
        amount=amount,
        currency=currency,
        payment_month=payment_month,
        reference=request.form.get("reference", "").strip()[:100] or None,
        proof_file=proof_path,
        status="pending",
    )
    db.session.add(payment)
    create_in_app_notification(
        tenancy.property.landlord_id,
        "rent_payment_submitted",
        "Rent payment proof submitted",
        f"{current_user.name} submitted rent payment proof for {payment_month} at {tenancy.property.title}.",
        url_for("landlord.rent_payments"),
        current_user.id,
    )
    db.session.commit()
    flash("Rent payment proof submitted for landlord review.", "success")
    return redirect(url_for("student.rent_payments"))


@student.route("/rent-payments/<int:payment_id>/proof")
@student_required
def download_rent_payment_proof(payment_id):
    payment = RentPayment.query.filter_by(id=payment_id, student_id=current_user.id).first_or_404()
    if not payment.proof_file:
        abort(404)
    return send_from_directory(
        current_app.config["PRIVATE_UPLOAD_FOLDER"],
        payment.proof_file,
        as_attachment=True,
        download_name=f"rent-payment-proof-{payment.id}{os.path.splitext(payment.proof_file)[1]}",
    )

@student.route("/maintenance")
@student_required
def maintenance():
    items = MaintenanceRequest.query.filter_by(reported_by_id=current_user.id).order_by(MaintenanceRequest.reported_at.desc()).all()
    tenancies = Tenancy.query.filter_by(student_id=current_user.id, status="active").order_by(Tenancy.created_at.desc()).all()
    return render_template("student/maintenance.html", requests=items, tenancies=tenancies)


@student.route("/tenancies/<int:tenancy_id>/maintenance", methods=["POST"])
@student_required
def report_maintenance(tenancy_id):
    tenancy = Tenancy.query.filter_by(id=tenancy_id, student_id=current_user.id, status="active").first_or_404()
    title = request.form.get("title", "").strip()[:200]
    description = request.form.get("description", "").strip()
    priority = request.form.get("priority", "normal").strip().lower()
    if not title or not description:
        flash("Add a title and description for the maintenance issue.", "danger")
    elif priority not in {"low", "normal", "high", "urgent"}:
        flash("Choose a valid priority.", "danger")
    else:
        item = MaintenanceRequest(
            property_id=tenancy.property_id,
            reported_by_id=current_user.id,
            title=title,
            description=description[:5000],
            priority=priority,
        )
        db.session.add(item)
        create_in_app_notification(
            tenancy.property.landlord_id,
            "maintenance_reported",
            "New maintenance request",
            f"{current_user.name} reported: {title} at {tenancy.property.title}.",
            url_for("landlord.maintenance"),
            current_user.id,
        )
        db.session.commit()
        flash("Your maintenance request has been sent to the landlord.", "success")
    return redirect(url_for("student.maintenance"))

@student.route("/tenancies")
@student_required
def tenancies():
    items = Tenancy.query.filter_by(student_id=current_user.id).order_by(Tenancy.created_at.desc()).all()
    offers = TenancyOffer.query.join(Application).filter(Application.student_id == current_user.id).order_by(TenancyOffer.created_at.desc()).all()
    return render_template("student/tenancies.html", tenancies=items, offers=offers)


@student.route("/applications/<int:application_id>/tenancy-offer/respond", methods=["POST"])
@student_required
def respond_to_tenancy_offer(application_id):
    application = Application.query.filter_by(id=application_id, student_id=current_user.id).first_or_404()
    offer = TenancyOffer.query.filter_by(application_id=application.id).first_or_404()
    response = request.form.get("response", "").strip().lower()
    if application.status != "approved" or offer.status != "proposed":
        flash("This tenancy offer is no longer awaiting your response.", "warning")
    elif response not in {"accepted", "declined"}:
        flash("Choose accept or decline.", "danger")
    elif response == "declined":
        offer.status = "declined"
        create_in_app_notification(
            application.property.landlord_id,
            "tenancy_offer_declined",
            "Tenancy offer declined",
            f"{current_user.name} declined the tenancy offer for {application.property.title}.",
            url_for("landlord.tenancies"),
            current_user.id,
        )
        db.session.commit()
        flash("You declined the offer. No tenancy has been created.", "info")
    elif Tenancy.query.filter_by(application_id=application.id).first():
        flash("A tenancy already exists for this application.", "warning")
    else:
        tenancy = Tenancy(application_id=application.id, property_id=application.property_id, student_id=current_user.id, room_label=offer.room_label, monthly_rent=offer.rent_amount if offer.rent_period == "month" else None, rent_amount=offer.rent_amount, rent_currency=offer.rent_currency, rent_period=offer.rent_period, start_date=offer.start_date, end_date=offer.end_date, status="active")
        offer.status = "accepted"
        db.session.add(tenancy)
        create_in_app_notification(
            application.property.landlord_id,
            "tenancy_offer_accepted",
            "Tenancy offer accepted",
            f"{current_user.name} accepted the tenancy offer for {application.property.title}. A tenancy record has been created.",
            url_for("landlord.tenancies"),
            current_user.id,
        )
        db.session.commit()
        flash("Offer accepted and tenancy record created. Complete any separate written rental agreement with the landlord.", "success")
    return redirect(url_for("student.tenancies"))

@student.route("/tenancies/<int:tenancy_id>/agreement")
@student_required
def rental_agreement(tenancy_id):
    tenancy = Tenancy.query.filter_by(
        id=tenancy_id,
        student_id=current_user.id
    ).first_or_404()
    offer = TenancyOffer.query.filter_by(application_id=tenancy.application_id, status="accepted").first()
    if not offer:
        flash("The accepted offer details for this tenancy could not be found.", "warning")
        return redirect(url_for("student.tenancies"))
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
        back_url=url_for("student.tenancies"),
    )



@student.route("/tenancies/<int:tenancy_id>/agreement/review", methods=["POST"])
@student_required
def review_rental_agreement(tenancy_id):
    tenancy = Tenancy.query.filter_by(id=tenancy_id, student_id=current_user.id).first_or_404()
    agreement = RentalAgreement.query.filter_by(tenancy_id=tenancy.id).first_or_404()
    if not record_review(agreement, "student"):
        flash("The signed agreement copy has already been uploaded; review is locked.", "warning")
    else:
        create_in_app_notification(
            tenancy.property.landlord_id,
            "agreement_reviewed",
            "Rental agreement reviewed",
            f"{current_user.name} recorded a review of the rental agreement for {tenancy.property.title}.",
            url_for("landlord.rental_agreement", tenancy_id=tenancy.id),
            current_user.id,
        )
        db.session.commit()
        flash("Your agreement review has been recorded.", "success")
    return redirect(url_for("student.rental_agreement", tenancy_id=tenancy.id))


@student.route("/tenancies/<int:tenancy_id>/agreement/signed-copy", methods=["POST"])
@student_required
def upload_signed_rental_agreement(tenancy_id):
    tenancy = Tenancy.query.filter_by(id=tenancy_id, student_id=current_user.id).first_or_404()
    agreement = RentalAgreement.query.filter_by(tenancy_id=tenancy.id).first_or_404()
    try:
        store_signed_pdf(agreement, request.files.get("signed_agreement"), current_user.id)
    except ValueError as exc:
        flash(str(exc), "danger")
        return redirect(url_for("student.rental_agreement", tenancy_id=tenancy.id))
    create_in_app_notification(
        tenancy.property.landlord_id,
        "agreement_signed_copy_uploaded",
        "Signed rental agreement copy uploaded",
        f"{current_user.name} uploaded a signed rental agreement copy for {tenancy.property.title}.",
        url_for("landlord.rental_agreement", tenancy_id=tenancy.id),
        current_user.id,
    )
    db.session.commit()
    flash("Signed PDF uploaded. HomeBridge has stored the document; it has not independently verified signatures or legal validity.", "success")
    return redirect(url_for("student.rental_agreement", tenancy_id=tenancy.id))


@student.route("/tenancies/<int:tenancy_id>/agreement/signed-copy")
@student_required
def download_signed_rental_agreement(tenancy_id):
    tenancy = Tenancy.query.filter_by(id=tenancy_id, student_id=current_user.id).first_or_404()
    agreement = RentalAgreement.query.filter_by(tenancy_id=tenancy.id).first_or_404()
    if not agreement.signed_document_path:
        return redirect(url_for("student.rental_agreement", tenancy_id=tenancy.id))
    return send_from_directory(
        current_app.config["PRIVATE_UPLOAD_FOLDER"],
        agreement.signed_document_path,
        as_attachment=True,
        download_name=f"homebridge-signed-agreement-{tenancy.id}.pdf",
    )

@student.route("/payments")
@student_required
def payment_history():
    payments = Payment.query.filter_by(user_id=current_user.id).order_by(Payment.submitted_at.desc()).all()
    return render_template("student/payments.html", payments=payments)


@student.route("/service-fee")
@student_required
def service_fee():
    fee = student_service_fee()
    currency = get_setting("student_service_fee_currency", "USD")
    pending = Payment.query.filter_by(user_id=current_user.id, payment_type="student_service_fee", status="pending").order_by(Payment.submitted_at.desc()).first()
    confirmed = has_confirmed_service_fee()
    return render_template("student/service_fee.html", fee=fee, currency=currency, pending_payment=pending, confirmed=confirmed, payment_details=current_app.config.get("PAYMENT_DETAILS", ""))


@student.route("/service-fee/pay", methods=["POST"])
@student_required
def submit_service_fee():
    fee = student_service_fee()
    currency = get_setting("student_service_fee_currency", "USD")
    if fee <= 0:
        flash("No student service fee is currently configured.", "info")
        return redirect(url_for("student.service_fee"))
    if has_confirmed_service_fee():
        flash("Your student service fee is already confirmed.", "success")
        return redirect(url_for("student.service_fee"))

    reference = request.form.get("reference", "").strip()
    if not reference:
        flash("Payment reference is required.", "danger")
        return redirect(url_for("student.service_fee"))
    if Payment.query.filter_by(reference=reference).first():
        flash("That payment reference has already been submitted.", "warning")
        return redirect(url_for("student.service_fee"))

    proof = request.files.get("proof_file")
    proof_file = save_payment_proof(proof) if proof and proof.filename else None
    if not proof_file:
        flash("Please upload proof of payment.", "danger")
        return redirect(url_for("student.service_fee"))

    payment = Payment(user_id=current_user.id, payment_type="student_service_fee", amount=fee, currency=currency, reference=reference, proof_file=proof_file, status="pending")
    db.session.add(payment)
    db.session.commit()
    flash("Payment submitted for admin verification. You can apply once it is confirmed.", "success")
    return redirect(url_for("student.service_fee"))


@student.route("/apply/<int:property_id>", methods=["POST"])
@student_required
def apply(property_id):
    prop = Property.query.filter_by(id=property_id, is_published=True, availability_status="available").first_or_404()
    if not has_confirmed_service_fee():
        flash("Please complete and have your student service fee confirmed before applying for accommodation.", "warning")
        return redirect(url_for("student.service_fee"))
    existing = Application.query.filter_by(property_id=prop.id, student_id=current_user.id).filter(Application.status.notin_(["withdrawn", "rejected"])).first()
    if existing:
        flash("You already have an active application for this property.", "warning")
        return redirect(url_for("public.property_detail", property_id=prop.id))
    application = Application(property_id=prop.id, student_id=current_user.id, message=request.form.get("message", "").strip())
    db.session.add(application)
    create_in_app_notification(
        prop.landlord_id,
        "new_application",
        "New accommodation application",
        f"{current_user.name} applied for {prop.title}. Review the application in your landlord dashboard.",
        url_for("landlord.dashboard"),
        current_user.id,
    )
    db.session.commit()
    flash("Your application has been submitted.", "success")
    return redirect(url_for("student.applications"))


@student.route("/applications")
@student_required
def applications():
    items = Application.query.filter_by(student_id=current_user.id).order_by(Application.submitted_at.desc()).all()
    return render_template("student/applications.html", applications=items)


@student.route("/applications/<int:application_id>/withdraw", methods=["POST"])
@student_required
def withdraw_application(application_id):
    application = Application.query.filter_by(id=application_id, student_id=current_user.id).first_or_404()
    if application.status not in {"pending", "under_review"}:
        flash("This application can no longer be withdrawn.", "warning")
        return redirect(url_for("student.applications"))
    application.status = "withdrawn"
    create_in_app_notification(
        application.property.landlord_id,
        "application_withdrawn",
        "Application withdrawn",
        f"{current_user.name} withdrew their application for {application.property.title}.",
        url_for("landlord.dashboard"),
        current_user.id,
    )
    db.session.commit()
    flash("Application withdrawn.", "success")
    return redirect(url_for("student.applications"))


@student.route("/applications/<int:application_id>/viewing/respond", methods=["POST"])
@student_required
def respond_to_viewing(application_id):
    application = Application.query.filter_by(id=application_id, student_id=current_user.id).first_or_404()
    appointment = ViewingAppointment.query.filter_by(application_id=application.id).first_or_404()
    response = request.form.get("response", "").strip().lower()
    if application.status != "approved" or appointment.status != "proposed":
        flash("This viewing proposal is no longer awaiting your response.", "warning")
    elif response not in {"confirmed", "declined"}:
        flash("Choose confirm or decline.", "danger")
    else:
        appointment.status = response
        create_in_app_notification(
            application.property.landlord_id,
            "viewing_response",
            "Viewing response received",
            f"{current_user.name} {response} the viewing for {application.property.title}.",
            url_for("landlord.application_detail", application_id=application.id),
            current_user.id,
        )
        db.session.commit()
        flash("Viewing " + ("confirmed." if response == "confirmed" else "declined."), "success")
    return redirect(url_for("student.applications"))
