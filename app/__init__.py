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

    env = os.environ.get("FLASK_ENV", "development")
    from config import ProductionConfig, DevelopmentConfig
    app.config.from_object(ProductionConfig if env == "production" else DevelopmentConfig)

    from app.models import User, db
    db.init_app(app)
    mail.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

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

    if not User.query.filter_by(role="admin").first():
        email = os.environ.get("ADMIN_EMAIL", "admin@example.com")
        admin = User(
            name=os.environ.get("ADMIN_NAME", "Administrator"),
            email=email,
            phone=os.environ.get("ADMIN_PHONE", ""),
            password=generate_password_hash(os.environ.get("ADMIN_PASSWORD", "change-me")),
            role="admin",
            is_approved=True,
        )
        db.session.add(admin)
        db.session.commit()
        print(f"Default admin created: {email}. Change the password immediately.")
