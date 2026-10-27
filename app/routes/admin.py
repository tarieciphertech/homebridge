from datetime import date, datetime, timedelta
from functools import wraps
import os

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from app.models import Application, Inquiry, Payment, PlatformSetting, Property, PropertyImage, User, db

admin_bp = Blueprint("admin_bp", __name__, url_prefix="/admin")


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            flash("Admin access required.", "danger")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated


def save_file(file, subfolder):
    filename = secure_filename(file.filename)
    folder = os.path.join(current_app.config["UPLOAD_FOLDER"], subfolder)
    os.makedirs(folder, exist_ok=True)
    file.save(os.path.join(folder, filename))
    return os.path.join(subfolder, filename)


def setting_value(key, default):
    setting = PlatformSetting.query.filter_by(key=key).first()
    return setting.value if setting else default


def save_setting(key, value):
    setting = PlatformSetting.query.filter_by(key=key).first()
    if setting:
        setting.value = value
    else:
        db.session.add(PlatformSetting(key=key, value=value))


@admin_bp.route("/dashboard")
@login_required
@admin_required
def dashboard():
    stats = {
        "students": User.query.filter_by(role="student").count(),
        "landlords": User.query.filter_by(role="landlord").count(),
        "pending_landlords": User.query.filter_by(role="landlord", is_approved=False).count(),
        "properties": Property.query.count(),
        "published_properties": Property.query.filter_by(is_published=True).count(),
        "pending_properties": Property.query.filter_by(is_verified=False).count(),
        "pending_payments": Payment.query.filter_by(status="pending").count(),
        "applications": Application.query.count(),
        "new_inquiries": Inquiry.query.filter_by(is_handled=False).count(),
    }
    recent_inquiries = Inquiry.query.order_by(Inquiry.submitted_at.desc()).limit(5).all()
    return render_template("admin/dashboard.html", stats=stats, recent_inquiries=recent_inquiries)


@admin_bp.route("/settings", methods=["GET", "POST"])
@login_required
@admin_required
def settings():
    if request.method == "POST":
        student_fee = request.form.get("student_service_fee", "0").strip()
        student_currency = request.form.get("student_service_fee_currency", "USD").strip().upper()
        landlord_fee = request.form.get("landlord_listing_fee", current_app.config.get("LISTING_FEE", 20)).strip()
        try:
            if float(student_fee) < 0 or float(landlord_fee) < 0:
                raise ValueError
        except ValueError:
            flash("Fees must be zero or a positive number.", "danger")
            return redirect(url_for("admin_bp.settings"))
        if not student_currency or len(student_currency) > 10:
            flash("Enter a valid fee currency.", "danger")
            return redirect(url_for("admin_bp.settings"))
        save_setting("student_service_fee", student_fee)
        save_setting("student_service_fee_currency", student_currency)
        save_setting("landlord_listing_fee", landlord_fee)
        db.session.commit()
        flash("Business fee settings updated.", "success")
        return redirect(url_for("admin_bp.settings"))

    return render_template(
        "admin/settings.html",
        student_service_fee=setting_value("student_service_fee", os.environ.get("STUDENT_SERVICE_FEE", "0")),
        student_service_fee_currency=setting_value("student_service_fee_currency", "USD"),
        landlord_listing_fee=setting_value("landlord_listing_fee", str(current_app.config.get("LISTING_FEE", 20))),
    )


@admin_bp.route("/landlords")
@login_required
@admin_required
def landlords():
    return render_template("admin/landlords.html", landlords=User.query.filter_by(role="landlord").order_by(User.created_at.desc()).all())


@admin_bp.route("/approve-landlord/<int:user_id>")
@login_required
@admin_required
def approve_landlord(user_id):
    landlord = User.query.filter_by(id=user_id, role="landlord").first_or_404()
    landlord.is_approved = True
    db.session.commit()
    flash("Landlord account approved.", "success")
    return redirect(url_for("admin_bp.landlords"))


@admin_bp.route("/revenue")
@login_required
@admin_required
def revenue():
    period = request.args.get("period", "30d")
    today = date.today()
    start_date = None
    end_date = today + timedelta(days=1)

    if period == "today":
        start_date = today
    elif period == "7d":
        start_date = today - timedelta(days=6)
    elif period == "30d":
        start_date = today - timedelta(days=29)
    elif period == "custom":
        try:
            start_date = date.fromisoformat(request.args.get("start_date", ""))
            last_day = date.fromisoformat(request.args.get("end_date", ""))
            if last_day < start_date:
                raise ValueError
            end_date = last_day + timedelta(days=1)
        except ValueError:
            flash("Choose a valid custom date range.", "warning")
            return redirect(url_for("admin_bp.revenue", period="30d"))
    else:
        period = "all"
        start_date = None
        end_date = None

    query = Payment.query
    if start_date:
        query = query.filter(Payment.submitted_at >= datetime.combine(start_date, datetime.min.time()))
    if end_date:
        query = query.filter(Payment.submitted_at < datetime.combine(end_date, datetime.min.time()))

    payments = query.order_by(Payment.submitted_at.desc()).all()

    # Pending/rejected totals are grouped by submission date; recognized revenue
    # is grouped by confirmation date, which reflects when the platform earned it.
    confirmed_query = Payment.query.filter(
        Payment.status == "confirmed", Payment.confirmed_at.isnot(None)
    )
    if start_date:
        confirmed_query = confirmed_query.filter(
            Payment.confirmed_at >= datetime.combine(start_date, datetime.min.time())
        )
    if end_date:
        confirmed_query = confirmed_query.filter(
            Payment.confirmed_at < datetime.combine(end_date, datetime.min.time())
        )

    status_totals = {}
    for status in ("confirmed", "pending", "rejected"):
        status_query = confirmed_query if status == "confirmed" else query.filter(Payment.status == status)
        rows = status_query.with_entities(
            Payment.currency, func.count(Payment.id), func.coalesce(func.sum(Payment.amount), 0)
        ).group_by(Payment.currency).all()
        status_totals[status] = [
            {"currency": currency, "count": count, "amount": amount}
            for currency, count, amount in rows
        ]

    rows = confirmed_query.with_entities(
        Payment.payment_type, Payment.currency, func.count(Payment.id),
        func.coalesce(func.sum(Payment.amount), 0)
    ).group_by(Payment.payment_type, Payment.currency).order_by(
        Payment.payment_type, Payment.currency
    ).all()

    return render_template(
        "admin/revenue.html",
        payments=payments,
        period=period,
        start_date=start_date.isoformat() if start_date else "",
        end_date=(end_date - timedelta(days=1)).isoformat() if end_date else "",
        status_totals=status_totals,
        confirmed_by_type=[
            {"payment_type": kind, "currency": currency, "count": count, "amount": amount}
            for kind, currency, count, amount in rows
        ],
    )


@admin_bp.route("/payments")
@login_required
@admin_required
def payments():
    status = request.args.get("status", "all")
    payment_type = request.args.get("type", "all")
    query = Payment.query
    if status in {"pending", "confirmed", "rejected"}:
        query = query.filter_by(status=status)
    else:
        status = "all"
    if payment_type in {"student_service_fee", "landlord_listing_fee"}:
        query = query.filter_by(payment_type=payment_type)
    else:
        payment_type = "all"
    payments = query.order_by(Payment.submitted_at.desc()).all()
    return render_template(
        "admin/payments.html", payments=payments,
        selected_status=status, selected_type=payment_type
    )


@admin_bp.route("/confirm-payment/<int:payment_id>", methods=["POST"])
@login_required
@admin_required
def confirm_payment(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    if payment.status != "pending":
        flash("Only pending payments can be confirmed.", "warning")
    else:
        payment.status = "confirmed"
        payment.confirmed_at = datetime.utcnow()
        db.session.commit()
        flash("Payment confirmed. Account approval remains a separate action.", "success")
    return redirect(request.referrer or url_for("admin_bp.payments"))


@admin_bp.route("/reject-payment/<int:payment_id>", methods=["POST"])
@login_required
@admin_required
def reject_payment(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    if payment.status != "pending":
        flash("Only pending payments can be rejected.", "warning")
    else:
        payment.status = "rejected"
        db.session.commit()
        flash("Payment rejected.", "warning")
    return redirect(request.referrer or url_for("admin_bp.payments"))


@admin_bp.route("/properties")
@login_required
@admin_required
def properties():
    items = Property.query.order_by(Property.submitted_at.desc()).all()
    return render_template("admin/properties.html", properties=items)


@admin_bp.route("/verify-property/<int:property_id>", methods=["POST"])
@login_required
@admin_required
def verify_property(property_id):
    prop = Property.query.get_or_404(property_id)
    prop.is_verified = True
    prop.is_published = False
    db.session.commit()
    flash("Property verified. It can now be published.", "success")
    return redirect(url_for("admin_bp.properties"))


@admin_bp.route("/reject-property/<int:property_id>", methods=["POST"])
@login_required
@admin_required
def reject_property(property_id):
    prop = Property.query.get_or_404(property_id)
    prop.is_verified = False
    prop.is_published = False
    prop.is_featured = False
    db.session.commit()
    flash("Property rejected and kept unpublished.", "warning")
    return redirect(url_for("admin_bp.properties"))


@admin_bp.route("/publish-property/<int:property_id>", methods=["POST"])
@login_required
@admin_required
def publish_property(property_id):
    prop = Property.query.get_or_404(property_id)
    if not prop.is_verified:
        flash("Verify the property before publishing it.", "warning")
        return redirect(url_for("admin_bp.properties"))
    prop.is_published = not prop.is_published
    if not prop.is_published:
        prop.is_featured = False
    db.session.commit()
    flash(f"Property {'published' if prop.is_published else 'unpublished'}.", "success")
    return redirect(url_for("admin_bp.properties"))


@admin_bp.route("/feature-property/<int:property_id>", methods=["POST"])
@login_required
@admin_required
def feature_property(property_id):
    prop = Property.query.get_or_404(property_id)
    if not prop.is_verified or not prop.is_published:
        flash("Only published, verified properties can be featured.", "warning")
        return redirect(url_for("admin_bp.properties"))
    prop.is_featured = not prop.is_featured
    db.session.commit()
    return redirect(url_for("admin_bp.properties"))


@admin_bp.route("/add-property", methods=["GET", "POST"])
@login_required
@admin_required
def add_property():
    if request.method == "POST":
        prop = Property(
            landlord_id=current_user.id,
            title=request.form.get("title"),
            description=request.form.get("description"),
            property_type=request.form.get("property_type", "house"),
            listing_type=request.form.get("listing_type", "rent"),
            price=request.form.get("price") or 0,
            location=request.form.get("location"),
            city=request.form.get("city"),
            country=request.form.get("country", "Zimbabwe"),
            bedrooms=request.form.get("bedrooms") or None,
            bathrooms=request.form.get("bathrooms") or None,
            available_rooms=request.form.get("available_rooms") or None,
            total_rooms=request.form.get("total_rooms") or None,
            size_sqm=request.form.get("size_sqm") or None,
            amenities=request.form.get("amenities"),
            house_rules=request.form.get("house_rules"),
            is_verified=True,
            is_published=True,
            is_featured=request.form.get("is_featured") == "on",
        )
        db.session.add(prop)
        db.session.flush()
        for img in request.files.getlist("images"):
            if img and img.filename:
                db.session.add(PropertyImage(property_id=prop.id, filename=save_file(img, "properties")))
        db.session.commit()
        flash("Property added and published.", "success")
        return redirect(url_for("admin_bp.properties"))
    return render_template("admin/add_property.html")


@admin_bp.route("/inquiries")
@login_required
@admin_required
def inquiries():
    return render_template("admin/inquiries.html", inquiries=Inquiry.query.order_by(Inquiry.submitted_at.desc()).all())


@admin_bp.route("/handle-inquiry/<int:inquiry_id>")
@login_required
@admin_required
def handle_inquiry(inquiry_id):
    inquiry = Inquiry.query.get_or_404(inquiry_id)
    inquiry.is_handled = True
    db.session.commit()
    return redirect(url_for("admin_bp.inquiries"))


@admin_bp.route("/change-password", methods=["POST"])
@login_required
@admin_required
def change_password():
    current_password = request.form.get("current_password", "")
    new_password = request.form.get("new_password", "")
    confirm = request.form.get("confirm_password", "")
    if not check_password_hash(current_user.password, current_password):
        flash("Current password incorrect.", "danger")
    elif new_password != confirm:
        flash("New passwords do not match.", "danger")
    elif len(new_password) < 6:
        flash("Password must be at least 6 characters.", "danger")
    else:
        current_user.password = generate_password_hash(new_password)
        db.session.commit()
        flash("Password updated.", "success")
    return redirect(url_for("admin_bp.dashboard"))
