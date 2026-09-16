from flask import Blueprint, render_template
from flask_login import current_user, login_required

from app.models import Application, MaintenanceRequest, Payment, Property, RentPayment

landlord = Blueprint("landlord", __name__, url_prefix="/landlord")


@landlord.route("/dashboard")
@login_required
def dashboard():
    if current_user.role != "landlord":
        from flask import redirect, url_for
        return redirect(url_for("auth.dashboard"))

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
