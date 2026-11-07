from flask import Flask
from flask_login import LoginManager
from flask_mail import Mail
import os

mail = Mail()
login_manager = LoginManager()


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
        required = {
            "SECRET_KEY": app.config.get("SECRET_KEY"),
            "DATABASE_URL": app.config.get("SQLALCHEMY_DATABASE_URI"),
        }
        missing = [key for key, value in required.items() if not value]
        if missing:
            raise RuntimeError(
                "Production startup blocked: set " + ", ".join(missing) + " in the environment."
            )
        if len(app.config["SECRET_KEY"]) < 32:
            raise RuntimeError("Production SECRET_KEY must contain at least 32 characters.")

    from app.models import User, db
    db.init_app(app)
    mail.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return User.query.get(int(user_id))
        except (TypeError, ValueError):
            return None

    from app.routes.public import public
    from app.routes.auth import auth
    from app.routes.student import student
    from app.routes.landlord import landlord
    from app.routes.admin import admin_bp

    app.register_blueprint(public)
    app.register_blueprint(auth)
    app.register_blueprint(student)
    app.register_blueprint(landlord)
    app.register_blueprint(admin_bp)

    os.makedirs(os.path.join(app.config["UPLOAD_FOLDER"], "properties"), exist_ok=True)
    os.makedirs(os.path.join(app.config["UPLOAD_FOLDER"], "proofs"), exist_ok=True)

    with app.app_context():
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
    )
    db.session.add(admin)
    db.session.commit()
    print("Initial HomeBridge administrator account created.")
