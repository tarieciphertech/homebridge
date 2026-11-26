from datetime import date, datetime, timedelta
from functools import wraps
import os

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, send_from_directory, url_for
from flask_login import current_user, login_required
from sqlalchemy import func
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from app.models import (
    AdminAuditLog, AdminRole, AdminUserRole, Application, Inquiry, Payment,
    PlatformSetting, Property, PropertyImage, RentalAgreement, User, db,
)
from app.admin_access import (
    ROLE_DEFINITIONS, assign_admin_role, record_admin_audit,
    require_endpoint_permission,
)
from app.notifications import create_in_app_notification

admin_bp = Blueprint("admin_bp", __name__, url_prefix="/admin")


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != "admin":
            flash("Admin access required.", "danger")
            return redirect(url_for("auth.login"))
        # Unknown endpoints are denied by default. Every admin route must have
        # an explicit permission entry in app.admin_access.ENDPOINT_PERMISSIONS.
        require_endpoint_permission(request.endpoint)
        return f(*args, **kwargs)
    return decorated


def save_file(file, subfolder):
    if subfolder != "properties":
        raise ValueError("Unsupported public upload location.")
    from app.media_uploads import store_property_image
    return store_property_image(file)


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
        "active_staff": User.query.filter_by(role="admin", is_active_account=True).count(),
    }
    recent_inquiries = Inquiry.query.order_by(Inquiry.submitted_at.desc()).limit(5).all()
    return render_template("admin/dashboard.html", stats=stats, recent_inquiries=recent_inquiries)


@admin_bp.route("/agreements")
@login_required
@admin_required
def agreements():
    items = RentalAgreement.query.order_by(RentalAgreement.updated_at.desc()).all()
    return render_template("admin/agreements.html", agreements=items)


@admin_bp.route("/agreements/<int:agreement_id>/signed-copy")
@login_required
@admin_required
def download_signed_agreement(agreement_id):
    agreement = RentalAgreement.query.get_or_404(agreement_id)
    if not agreement.signed_document_path:
        flash("No signed copy has been uploaded for this agreement.", "info")
        return redirect(url_for("admin_bp.agreements"))
    record_admin_audit(
        "agreement.signed_copy.download",
        "rental_agreement",
        agreement.id,
        "Downloaded a signed rental agreement.",
    )
    db.session.commit()
    return send_from_directory(
        current_app.config["PRIVATE_UPLOAD_FOLDER"],
        agreement.signed_document_path,
        as_attachment=True,
        download_name=f"homebridge-signed-agreement-{agreement.tenancy_id}.pdf",
    )


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
        before = {
            "student_service_fee": setting_value("student_service_fee", os.environ.get("STUDENT_SERVICE_FEE", "0")),
            "student_service_fee_currency": setting_value("student_service_fee_currency", "USD"),
            "landlord_listing_fee": setting_value("landlord_listing_fee", str(current_app.config.get("LISTING_FEE", 20))),
        }
        save_setting("student_service_fee", student_fee)
        save_setting("student_service_fee_currency", student_currency)
        save_setting("landlord_listing_fee", landlord_fee)
        record_admin_audit(
            "settings.platform_fees.update", "platform_settings", "fees",
            "Updated platform service and listing fees.", before=before,
            after={
                "student_service_fee": student_fee,
                "student_service_fee_currency": student_currency,
                "landlord_listing_fee": landlord_fee,
            },
        )
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


@admin_bp.route("/approve-landlord/<int:user_id>", methods=["POST"])
@login_required
@admin_required
def approve_landlord(user_id):
    landlord = User.query.filter_by(id=user_id, role="landlord").first_or_404()
    before = {"is_approved": landlord.is_approved}
    landlord.is_approved = True
    record_admin_audit(
        "user.landlord.approve", "user", landlord.id,
        "Approved a landlord account.", before=before, after={"is_approved": True},
    )
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


@admin_bp.route("/payments/<int:payment_id>/proof")
@login_required
@admin_required
def payment_proof(payment_id):
    from pathlib import PurePosixPath

    payment = Payment.query.get_or_404(payment_id)
    if not payment.proof_file:
        abort(404)
    relative = PurePosixPath(payment.proof_file)
    if relative.is_absolute() or ".." in relative.parts or not relative.parts:
        abort(404)

    if relative.parts[0] == "platform-payments":
        record_admin_audit(
            "payment.proof.download", "platform_payment", payment.id,
            "Downloaded a private platform-payment proof.",
        )
        db.session.commit()
        return send_from_directory(
            current_app.config["PRIVATE_UPLOAD_FOLDER"],
            str(relative),
            as_attachment=True,
            download_name=f"platform-payment-proof-{payment.id}{relative.suffix.lower()}",
        )
    if relative.parts[0] == "proofs" and len(relative.parts) == 2:
        record_admin_audit(
            "payment.proof.download", "platform_payment", payment.id,
            "Downloaded a legacy platform-payment proof.",
        )
        db.session.commit()
        return send_from_directory(
            os.path.join(current_app.config["UPLOAD_FOLDER"], "proofs"),
            relative.parts[1],
            as_attachment=True,
            download_name=f"platform-payment-proof-{payment.id}{PurePosixPath(relative.parts[1]).suffix.lower()}",
        )
    abort(404)


@admin_bp.route("/confirm-payment/<int:payment_id>", methods=["POST"])
@login_required
@admin_required
def confirm_payment(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    if payment.status != "pending":
        flash("Only pending payments can be confirmed.", "warning")
    else:
        before = {"status": payment.status, "confirmed_at": payment.confirmed_at}
        payment.status = "confirmed"
        payment.confirmed_at = datetime.utcnow()
        target = (
            url_for("student.service_fee")
            if payment.payment_type == "student_service_fee"
            else url_for("landlord.listing_fee_page")
        )
        create_in_app_notification(
            payment.user_id,
            "platform_payment_confirmed",
            "HomeBridge payment confirmed",
            "Your HomeBridge platform payment has been confirmed. Any separate account or property approval still applies.",
            target,
            current_user.id,
        )
        record_admin_audit(
            "payment.confirm", "platform_payment", payment.id,
            "Confirmed a platform payment.", before=before,
            after={"status": payment.status, "confirmed_at": payment.confirmed_at},
        )
        db.session.commit()
        flash("Payment confirmed. Account or property approval remains a separate action.", "success")
    return redirect(url_for("admin_bp.payments"))


@admin_bp.route("/reject-payment/<int:payment_id>", methods=["POST"])
@login_required
@admin_required
def reject_payment(payment_id):
    payment = Payment.query.get_or_404(payment_id)
    if payment.status != "pending":
        flash("Only pending payments can be rejected.", "warning")
    else:
        before = {"status": payment.status}
        payment.status = "rejected"
        target = (
            url_for("student.service_fee")
            if payment.payment_type == "student_service_fee"
            else url_for("landlord.listing_fee_page")
        )
        create_in_app_notification(
            payment.user_id,
            "platform_payment_rejected",
            "HomeBridge payment needs attention",
            "Your HomeBridge platform payment was not confirmed. Please review the payment details and contact support if you need help.",
            target,
            current_user.id,
        )
        record_admin_audit(
            "payment.reject", "platform_payment", payment.id,
            "Rejected a platform payment.", before=before, after={"status": payment.status},
        )
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
    before = {"is_verified": prop.is_verified, "is_published": prop.is_published}
    prop.is_verified = True
    prop.is_published = False
    record_admin_audit(
        "property.verify", "property", prop.id, "Verified a property listing.",
        before=before, after={"is_verified": True, "is_published": False},
    )
    db.session.commit()
    flash("Property verified. It can now be published.", "success")
    return redirect(url_for("admin_bp.properties"))


@admin_bp.route("/reject-property/<int:property_id>", methods=["POST"])
@login_required
@admin_required
def reject_property(property_id):
    prop = Property.query.get_or_404(property_id)
    before = {
        "is_verified": prop.is_verified,
        "is_published": prop.is_published,
        "is_featured": prop.is_featured,
    }
    prop.is_verified = False
    prop.is_published = False
    prop.is_featured = False
    record_admin_audit(
        "property.reject", "property", prop.id, "Rejected a property listing.",
        before=before,
        after={"is_verified": False, "is_published": False, "is_featured": False},
    )
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
    before = {"is_published": prop.is_published, "is_featured": prop.is_featured}
    prop.is_published = not prop.is_published
    if not prop.is_published:
        prop.is_featured = False
    record_admin_audit(
        "property.publish.toggle", "property", prop.id,
        "Changed property publication status.", before=before,
        after={"is_published": prop.is_published, "is_featured": prop.is_featured},
    )
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
    before = {"is_featured": prop.is_featured}
    prop.is_featured = not prop.is_featured
    record_admin_audit(
        "property.feature.toggle", "property", prop.id,
        "Changed property featured status.", before=before,
        after={"is_featured": prop.is_featured},
    )
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
        try:
            for img in request.files.getlist("images"):
                if img and img.filename:
                    db.session.add(PropertyImage(property_id=prop.id, filename=save_file(img, "properties")))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), "danger")
            return render_template("admin/add_property.html")
        record_admin_audit(
            "property.create", "property", prop.id,
            "Created a property listing on behalf of the platform.",
            after={"title": prop.title, "city": prop.city, "is_published": prop.is_published},
        )
        db.session.commit()
        flash("Property added and published.", "success")
        return redirect(url_for("admin_bp.properties"))
    return render_template("admin/add_property.html")


@admin_bp.route("/inquiries")
@login_required
@admin_required
def inquiries():
    return render_template("admin/inquiries.html", inquiries=Inquiry.query.order_by(Inquiry.submitted_at.desc()).all())


@admin_bp.route("/handle-inquiry/<int:inquiry_id>", methods=["POST"])
@login_required
@admin_required
def handle_inquiry(inquiry_id):
    inquiry = Inquiry.query.get_or_404(inquiry_id)
    before = {"is_handled": inquiry.is_handled}
    inquiry.is_handled = True
    record_admin_audit(
        "inquiry.handle", "inquiry", inquiry.id,
        "Marked a public inquiry as handled.", before=before, after={"is_handled": True},
    )
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
    elif len(new_password) < 16:
        flash("Administrator passwords must be at least 16 characters.", "danger")
    else:
        current_user.password = generate_password_hash(new_password)
        current_user.must_change_password = False
        record_admin_audit(
            "staff.password.change", "admin_staff", current_user.id,
            "Changed own administrator password.",
        )
        db.session.commit()
        flash("Password updated.", "success")
    return redirect(url_for("admin_bp.dashboard"))

@admin_bp.route("/staff")
@login_required
@admin_required
def staff():
    members = User.query.filter_by(role="admin").order_by(User.created_at.desc()).all()
    assignments = AdminUserRole.query.filter(
        AdminUserRole.user_id.in_([member.id for member in members] or [-1])
    ).all()
    roles_by_user = {assignment.user_id: assignment.role for assignment in assignments}
    return render_template(
        "admin/staff.html",
        staff_members=members,
        roles=AdminRole.query.order_by(AdminRole.id).all(),
        roles_by_user=roles_by_user,
    )


@admin_bp.route("/staff/create", methods=["POST"])
@login_required
@admin_required
def create_staff():
    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    phone = request.form.get("phone", "").strip()
    password = request.form.get("password", "")
    role_key = request.form.get("role_key", "").strip()

    if not name or len(name) > 150 or "@" not in email or len(email) > 120 or len(phone) > 30:
        flash("Enter a valid staff name, email address, and phone number.", "danger")
        return redirect(url_for("admin_bp.staff"))
    if len(password) < 16:
        flash("Initial staff passwords must be at least 16 characters.", "danger")
        return redirect(url_for("admin_bp.staff"))
    if role_key not in ROLE_DEFINITIONS:
        flash("Choose a valid staff role.", "danger")
        return redirect(url_for("admin_bp.staff"))
    if User.query.filter_by(email=email).first():
        flash("An account with that email already exists.", "danger")
        return redirect(url_for("admin_bp.staff"))

    member = User(
        name=name,
        email=email,
        phone=phone,
        password=generate_password_hash(password),
        role="admin",
        is_approved=True,
        is_active_account=True,
        must_change_password=True,
    )
    db.session.add(member)
    db.session.flush()
    assign_admin_role(member, role_key, current_user.id)
    record_admin_audit(
        "staff.create", "admin_staff", member.id,
        "Created an administrator staff account.",
        after={"email": member.email, "role": role_key, "active": True, "must_change_password": True},
    )
    db.session.commit()
    flash("Staff account created. The staff member must change the initial password at first login.", "success")
    return redirect(url_for("admin_bp.staff"))


@admin_bp.route("/staff/<int:user_id>/role", methods=["POST"])
@login_required
@admin_required
def change_staff_role(user_id):
    member = User.query.filter_by(id=user_id, role="admin").first_or_404()
    if member.id == current_user.id:
        flash("You cannot change your own administrator role.", "danger")
        return redirect(url_for("admin_bp.staff"))

    role_key = request.form.get("role_key", "").strip()
    if role_key not in ROLE_DEFINITIONS:
        flash("Choose a valid administrator role.", "danger")
        return redirect(url_for("admin_bp.staff"))

    assignment = AdminUserRole.query.filter_by(user_id=member.id).first()
    previous_key = assignment.role.key if assignment and assignment.role else None
    if previous_key == "super_admin" and member.is_active_account and role_key != "super_admin":
        active_super_admins = (
            AdminUserRole.query.join(AdminRole, AdminRole.id == AdminUserRole.role_id)
            .join(User, User.id == AdminUserRole.user_id)
            .filter(AdminRole.key == "super_admin", User.role == "admin", User.is_active_account.is_(True))
            .count()
        )
        if active_super_admins <= 1:
            flash("The last active Super Admin cannot be demoted.", "danger")
            return redirect(url_for("admin_bp.staff"))

    before = {"role": previous_key}
    assign_admin_role(member, role_key, current_user.id)
    record_admin_audit(
        "staff.role.change", "admin_staff", member.id,
        "Changed an administrator staff role.", before=before, after={"role": role_key},
    )
    db.session.commit()
    flash("Administrator role updated.", "success")
    return redirect(url_for("admin_bp.staff"))


@admin_bp.route("/staff/<int:user_id>/status", methods=["POST"])
@login_required
@admin_required
def toggle_staff_status(user_id):
    member = User.query.filter_by(id=user_id, role="admin").first_or_404()
    if member.id == current_user.id:
        flash("You cannot suspend your own administrator account.", "danger")
        return redirect(url_for("admin_bp.staff"))

    assignment = AdminUserRole.query.filter_by(user_id=member.id).first()
    role_key = assignment.role.key if assignment and assignment.role else None
    next_active = not member.is_active_account
    if not next_active and role_key == "super_admin":
        active_super_admins = (
            AdminUserRole.query.join(AdminRole, AdminRole.id == AdminUserRole.role_id)
            .join(User, User.id == AdminUserRole.user_id)
            .filter(AdminRole.key == "super_admin", User.role == "admin", User.is_active_account.is_(True))
            .count()
        )
        if active_super_admins <= 1:
            flash("The last active Super Admin cannot be suspended.", "danger")
            return redirect(url_for("admin_bp.staff"))

    before = {"is_active_account": member.is_active_account}
    member.is_active_account = next_active
    record_admin_audit(
        "staff.status.change", "admin_staff", member.id,
        "Reactivated an administrator account." if next_active else "Suspended an administrator account.",
        before=before, after={"is_active_account": next_active},
    )
    db.session.commit()
    flash("Staff account reactivated." if next_active else "Staff account suspended.", "success")
    return redirect(url_for("admin_bp.staff"))


@admin_bp.route("/audit")
@login_required
@admin_required
def audit():
    page = request.args.get("page", 1, type=int)
    action = request.args.get("action", "").strip()[:100]
    query = AdminAuditLog.query.order_by(AdminAuditLog.created_at.desc(), AdminAuditLog.id.desc())
    if action:
        query = query.filter(AdminAuditLog.action.ilike(f"%{action}%"))
    logs = query.paginate(page=max(page, 1), per_page=50, error_out=False)
    return render_template("admin/audit.html", logs=logs, selected_action=action)


@admin_bp.route("/force-change-password", methods=["GET", "POST"])
@login_required
@admin_required
def force_change_password():
    if not current_user.must_change_password:
        return redirect(url_for("admin_bp.dashboard"))
    if request.method == "POST":
        current_password = request.form.get("current_password", "")
        new_password = request.form.get("new_password", "")
        confirm = request.form.get("confirm_password", "")
        if not check_password_hash(current_user.password, current_password):
            flash("Current password incorrect.", "danger")
        elif new_password != confirm:
            flash("New passwords do not match.", "danger")
        elif len(new_password) < 16:
            flash("Administrator passwords must be at least 16 characters.", "danger")
        else:
            current_user.password = generate_password_hash(new_password)
            current_user.must_change_password = False
            record_admin_audit(
                "staff.password.initial_change", "admin_staff", current_user.id,
                "Completed the required first-login password change.",
            )
            db.session.commit()
            flash("Password updated. Welcome to HomeBridge administration.", "success")
            return redirect(url_for("admin_bp.dashboard"))
    return render_template("admin/force_change_password.html")

