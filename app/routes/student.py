from flask import Blueprint, render_template
from flask_login import current_user, login_required

from app.models import Application, Payment, Property

student = Blueprint("student", __name__, url_prefix="/student")


@student.route("/dashboard")
@login_required
def dashboard():
    if current_user.role != "student":
        from flask import redirect, url_for
        return redirect(url_for("auth.dashboard"))

    applications = (
        Application.query.filter_by(student_id=current_user.id)
        .order_by(Application.submitted_at.desc())
        .limit(10)
        .all()
    )
    payments = (
        Payment.query.filter_by(user_id=current_user.id)
        .order_by(Payment.submitted_at.desc())
        .limit(10)
        .all()
    )
    featured = (
        Property.query.filter_by(is_published=True)
        .order_by(Property.is_featured.desc(), Property.submitted_at.desc())
        .limit(6)
        .all()
    )
    return render_template(
        "student/dashboard.html",
        applications=applications,
        payments=payments,
        featured_properties=featured,
    )
