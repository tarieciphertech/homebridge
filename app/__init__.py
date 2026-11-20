from flask import Flask, abort, request
from flask_login import LoginManager
from flask_mail import Mail
from flask_wtf.csrf import CSRFProtect
import os

mail = Mail()
login_manager = LoginManager()
csrf = CSRFProtect()


def create_app():
    app = Flask(__name__)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    env = os.environ.get("FLASK_ENV", "development").strip().lower()
    from config import ProductionConfig, DevelopmentConfig
    app.config.from_object(ProductionConfig if env == "production" else DevelopmentConfig)

    if env == "production":
        secret_key = os.environ.get("SECRET_KEY", "").strip()
        database_url = os.environ.get("DATABASE_URL", "").strip()
        missing = [
            key for key, value in {
                "SECRET_KEY": secret_key,
                "DATABASE_URL": database_url,
            }.items() if not value
        ]
        if missing:
            raise RuntimeError(
                "Production startup blocked: set " + ", ".join(missing) + " in the environment."
            )
        if len(secret_key) < 32:
            raise RuntimeError("Production SECRET_KEY must contain at least 32 characters.")
        app.config["SECRET_KEY"] = secret_key
        app.config["SQLALCHEMY_DATABASE_URI"] = database_url

    from app.models import User, db
    db.init_app(app)
    mail.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None

    from app.routes.public import public
    from app.routes.auth import auth
    from app.routes.student import student
    from app.routes.landlord import landlord
    from app.routes.admin import admin_bp
    from app.routes.notifications import notifications_bp

    app.register_blueprint(public)
    app.register_blueprint(auth)
    app.register_blueprint(student)
    app.register_blueprint(landlord)
    app.register_blueprint(admin_bp)
    app.register_blueprint(notifications_bp)

    @app.before_request
    def block_sensitive_static_uploads():
        # Flask's built-in /static route bypasses the public /uploads route.
        # Only property photographs may be served from the static uploads tree.
        if request.endpoint == "static":
            filename = (request.view_args or {}).get("filename", "").replace("\\", "/")
            parts = [part for part in filename.split("/") if part]
            if parts and parts[0] == "uploads" and (len(parts) < 2 or parts[1] != "properties"):
                abort(404)

    @app.context_processor
    def inject_notification_count():
        from flask_login import current_user
        from app.models import Notification
        count = 0
        if current_user.is_authenticated:
            count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        return {"unread_notification_count": count}

    os.makedirs(os.path.join(app.config["UPLOAD_FOLDER"], "properties"), exist_ok=True)
    os.makedirs(os.path.join(app.config["UPLOAD_FOLDER"], "proofs"), exist_ok=True)
    os.makedirs(app.config["PRIVATE_UPLOAD_FOLDER"], mode=0o700, exist_ok=True)
    os.chmod(app.config["PRIVATE_UPLOAD_FOLDER"], 0o700)

    with app.app_context():
        # Production schema changes are applied only through reviewed SQL
        # migrations. create_all is retained for local development and CI.
        if env != "production":
            db.create_all()
        create_default_admin()

    return app


def create_default_admin():
    from app.models import User, db
    from werkzeug.security import generate_password_hash

    if User.query.filter_by(role="admin").first():
        return

    email = os.environ.get("ADMIN_EMAIL", "").strip().lower()
    password = os.environ.get("ADMIN_PASSWORD", "")
    name = os.environ.get("ADMIN_NAME", "HomeBridge Administrator").strip()

    if not email or not password:
        if os.environ.get("FLASK_ENV", "development").strip().lower() == "production":
            raise RuntimeError(
                "Production startup blocked: no admin account exists. Set ADMIN_EMAIL and "
                "a strong ADMIN_PASSWORD for the initial administrator."
            )
        print("No admin account created: set ADMIN_EMAIL and ADMIN_PASSWORD to provision one.")
        return

    if email == "admin@example.com" or len(password) < 16:
        raise RuntimeError(
            "Administrator provisioning requires a non-placeholder email and a password "
            "of at least 16 characters."
        )

    admin = User(
        name=name,
        email=email,
        phone=os.environ.get("ADMIN_PHONE", ""),
        password=generate_password_hash(password),
        role="admin",
        is_approved=True,
        is_active_account=True,
    )
    db.session.add(admin)
    db.session.commit()
    print("Initial HomeBridge administrator account created.")
