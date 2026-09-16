from datetime import datetime
from functools import wraps
import os

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from app.models import Application, Inquiry, Payment, Property, PropertyImage, User, db

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


@admin_bp.route("/payments")
@login_required
@admin_required
def payments():
    return render_template("admin/payments.html", payments=Payment.query.order_by(Payment.submitted_at.desc()).all())


@admin_bp.route("/confirm-payment/<int:payment_id>")
@login_required
@admin_required
def confirm_payment(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    payment.status = "confirmed"
    payment.confirmed_at = datetime.utcnow()
    if payment.payment_type == "landlord_listing_fee":
        user = User.query.get(payment.user_id)
        if user:
            user.is_approved = True
    db.session.commit()
    flash("Payment confirmed.", "success")
    return redirect(url_for("admin_bp.payments"))


@admin_bp.route("/reject-payment/<int:payment_id>")
@login_required
@admin_required
def reject_payment(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    payment.status = "rejected"
    db.session.commit()
    flash("Payment rejected.", "warning")
    return redirect(url_for("admin_bp.payments"))


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
