from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.models import Application, Payment, Property, db

student = Blueprint("student", __name__, url_prefix="/student")


def student_required(view):
    from functools import wraps

    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if current_user.role != "student":
            return redirect(url_for("auth.dashboard"))
        return view(*args, **kwargs)

    return wrapped


@student.route("/dashboard")
@student_required
def dashboard():
    applications = Application.query.filter_by(student_id=current_user.id).order_by(Application.submitted_at.desc()).limit(10).all()
    payments = Payment.query.filter_by(user_id=current_user.id).order_by(Payment.submitted_at.desc()).limit(10).all()
    featured = Property.query.filter_by(is_published=True, availability_status="available").order_by(Property.is_featured.desc(), Property.submitted_at.desc()).limit(6).all()
    return render_template("student/dashboard.html", applications=applications, payments=payments, featured_properties=featured)


@student.route("/apply/<int:property_id>", methods=["POST"])
@student_required
def apply(property_id):
    prop = Property.query.filter_by(id=property_id, is_published=True, availability_status="available").first_or_404()
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
