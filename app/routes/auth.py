from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from werkzeug.security import check_password_hash, generate_password_hash

from app.models import User, db
from app.notifications import notify_new_landlord

auth = Blueprint("auth", __name__)


@auth.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("auth.dashboard"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        phone = request.form.get("phone", "").strip()
        password = request.form.get("password", "")
        account_type = request.form.get("role", "student").strip().lower()

        if account_type not in {"student", "professional", "family", "individual", "landlord"}:
            flash("Please select a valid account type.", "danger")
            return redirect(url_for("auth.register"))
        if not name or not email:
            flash("Name and email are required.", "danger")
            return redirect(url_for("auth.register"))
        if len(password) < 6:
            flash("Password must be at least 6 characters.", "danger")
            return redirect(url_for("auth.register"))
        if User.query.filter_by(email=email).first():
            flash("Email already registered. Please login.", "danger")
            return redirect(url_for("auth.login"))

        # All seeker categories retain the established student role internally.
        is_landlord = account_type == "landlord"
        user = User(
            name=name,
            email=email,
            phone=phone,
            password=generate_password_hash(password),
            role="landlord" if is_landlord else "student",
            seeker_type=None if is_landlord else account_type,
            is_approved=not is_landlord,
        )
        db.session.add(user)
        db.session.commit()

        if is_landlord:
            try:
                notify_new_landlord(user)
            except Exception:
                pass
            flash("Landlord account created. Your account will be reviewed before you can publish properties.", "success")
        else:
            flash("Accommodation seeker account created successfully.", "success")

        login_user(user)
        return redirect(url_for("auth.dashboard"))

    return render_template("auth/register.html")


@auth.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("auth.dashboard"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        user = User.query.filter_by(email=email).first()
        if not user or not check_password_hash(user.password, request.form.get("password", "")):
            flash("Invalid email or password.", "danger")
            return redirect(url_for("auth.login"))
        if not user.is_active_account:
            flash("This account is currently inactive.", "danger")
            return redirect(url_for("auth.login"))

        login_user(user)
        return redirect(url_for("auth.dashboard"))

    return render_template("auth/login.html")


@auth.route("/dashboard")
@login_required
def dashboard():
    if current_user.role == "admin":
        return redirect(url_for("admin_bp.dashboard"))
    if current_user.role == "landlord":
        return redirect(url_for("landlord.dashboard"))
    return redirect(url_for("student.dashboard"))


@auth.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("public.properties"))
