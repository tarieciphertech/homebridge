from datetime import datetime

from flask_login import UserMixin
from flask_sqlalchemy import SQLAlchemy


db = SQLAlchemy()


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone = db.Column(db.String(30))
    password = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="student", index=True)
    is_approved = db.Column(db.Boolean, default=False, nullable=False)
    is_active_account = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    properties = db.relationship("Property", back_populates="landlord", foreign_keys="Property.landlord_id")
    payments = db.relationship("Payment", back_populates="user", foreign_keys="Payment.user_id")


class Property(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    landlord_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    property_type = db.Column(db.String(50), nullable=False, default="house")
    listing_type = db.Column(db.String(20), nullable=False, default="rent")
    price = db.Column(db.Numeric(12, 2), nullable=False)
    location = db.Column(db.String(200), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    country = db.Column(db.String(100), default="Zimbabwe", nullable=False)
    bedrooms = db.Column(db.Integer)
    bathrooms = db.Column(db.Integer)
    available_rooms = db.Column(db.Integer)
    total_rooms = db.Column(db.Integer)
    size_sqm = db.Column(db.Numeric(10, 2))
    amenities = db.Column(db.Text)
    house_rules = db.Column(db.Text)
    is_verified = db.Column(db.Boolean, default=False, nullable=False)
    is_published = db.Column(db.Boolean, default=False, nullable=False)
    is_featured = db.Column(db.Boolean, default=False, nullable=False)
    availability_status = db.Column(db.String(30), default="available", nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    landlord = db.relationship("User", back_populates="properties", foreign_keys=[landlord_id])
    images = db.relationship("PropertyImage", back_populates="property", lazy=True, cascade="all, delete-orphan")
    applications = db.relationship("Application", back_populates="property", lazy=True, cascade="all, delete-orphan")
    maintenance_requests = db.relationship("MaintenanceRequest", back_populates="property", lazy=True, cascade="all, delete-orphan")
    rent_payments = db.relationship("RentPayment", back_populates="property", lazy=True, cascade="all, delete-orphan")

    @property
    def main_image(self):
        return self.images[0].filename if self.images else None


class PropertyImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey("property.id"), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    property = db.relationship("Property", back_populates="images")


class Payment(db.Model):
    """Platform payments such as student service fees and landlord listing fees."""
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    payment_type = db.Column(db.String(40), nullable=False, default="student_service_fee")
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(10), default="USD", nullable=False)
    reference = db.Column(db.String(100), unique=True, nullable=True)
    proof_file = db.Column(db.String(255))
    status = db.Column(db.String(20), default="pending", nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    confirmed_at = db.Column(db.DateTime)

    user = db.relationship("User", back_populates="payments", foreign_keys=[user_id])


class Application(db.Model):
    """A student's application/inquiry for a specific property."""
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey("property.id"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    message = db.Column(db.Text)
    status = db.Column(db.String(30), default="pending", nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    property = db.relationship("Property", back_populates="applications")
    student = db.relationship("User", foreign_keys=[student_id], backref="applications")


class Tenancy(db.Model):
    """Active or historical student tenancy at a property."""
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey("property.id"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    room_label = db.Column(db.String(100))
    monthly_rent = db.Column(db.Numeric(12, 2), nullable=False)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date)
    status = db.Column(db.String(30), default="active", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    property = db.relationship("Property", backref=db.backref("tenancies", lazy=True))
    student = db.relationship("User", foreign_keys=[student_id], backref="tenancies")


class RentPayment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    tenancy_id = db.Column(db.Integer, db.ForeignKey("tenancy.id"), nullable=False, index=True)
    property_id = db.Column(db.Integer, db.ForeignKey("property.id"), nullable=False, index=True)
    student_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, index=True)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    currency = db.Column(db.String(10), default="USD", nullable=False)
    payment_month = db.Column(db.String(7), nullable=False)
    reference = db.Column(db.String(100))
    proof_file = db.Column(db.String(255))
    status = db.Column(db.String(20), default="pending", nullable=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    confirmed_at = db.Column(db.DateTime)

    tenancy = db.relationship("Tenancy", backref=db.backref("rent_payments", lazy=True))
    property = db.relationship("Property", back_populates="rent_payments")
    student = db.relationship("User", foreign_keys=[student_id], backref="rent_payments")


class MaintenanceRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey("property.id"), nullable=False, index=True)
    reported_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    priority = db.Column(db.String(20), default="normal", nullable=False)
    status = db.Column(db.String(30), default="open", nullable=False)
    resolution_notes = db.Column(db.Text)
    cost = db.Column(db.Numeric(12, 2))
    reported_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = db.Column(db.DateTime)

    property = db.relationship("Property", back_populates="maintenance_requests")
    reported_by = db.relationship("User", foreign_keys=[reported_by_id], backref="maintenance_requests")


class Inquiry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    visitor_name = db.Column(db.String(100))
    visitor_email = db.Column(db.String(120))
    visitor_phone = db.Column(db.String(30))
    inquiry_type = db.Column(db.String(30), default="property", nullable=False)
    reference_id = db.Column(db.Integer, nullable=True)
    message = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_handled = db.Column(db.Boolean, default=False, nullable=False)
