import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 300}
    BASEDIR = os.path.abspath(os.path.dirname(__file__))
    UPLOAD_FOLDER = os.path.join(BASEDIR, "app/static/uploads")
    PRIVATE_UPLOAD_FOLDER = os.environ.get(
        "PRIVATE_UPLOAD_FOLDER",
        os.path.join(os.path.dirname(BASEDIR), "homebridge-private-uploads"),
    )
    MAX_CONTENT_LENGTH = 32 * 1024 * 1024
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "smtp.zoho.com")
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USE_TLS = os.environ.get("MAIL_USE_TLS", "true").lower() in {"1", "true", "yes"}
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.environ.get("MAIL_DEFAULT_SENDER") or MAIL_USERNAME
    ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL")
    ADMIN_PHONE = os.environ.get("ADMIN_PHONE", "")
    LISTING_FEE = float(os.environ.get("LISTING_FEE", "20"))
    PAYMENT_DETAILS = os.environ.get("PAYMENT_DETAILS", "")


class DevelopmentConfig(Config):
    DEBUG = True
    SECRET_KEY = os.environ.get("SECRET_KEY", "local-development-only-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or (
        "sqlite:///" + os.path.join(os.path.abspath(os.path.dirname(__file__)), "property_management.db")
    )


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    REMEMBER_COOKIE_SECURE = True
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SAMESITE = "Lax"
