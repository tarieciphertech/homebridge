from functools import wraps
import os
from uuid import uuid4

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename

from app.models import Application, Payment, PlatformSetting, Property, db

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
    return render_template("student/dashboard.html", applications=applications, payments=payments, featured_properties=featured, service_fee=student_service_fee(), service_fee_paid=has_confirmed_service_fee())


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
    db.session.commit()
    flash("Application withdrawn.", "success")
    return redirect(url_for("student.applications"))
