from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(30))
    password = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default='agent')
    is_approved = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    amount = db.Column(db.Float)
    proof_file = db.Column(db.String(255))
    status = db.Column(db.String(20), default='pending')
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    confirmed_at = db.Column(db.DateTime, nullable=True)
    user = db.relationship('User', backref='payments', foreign_keys=[user_id])

class Property(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    property_type = db.Column(db.String(50))
    listing_type = db.Column(db.String(20))
    price = db.Column(db.String(100))
    location = db.Column(db.String(200))
    city = db.Column(db.String(100))
    country = db.Column(db.String(100), default='Zimbabwe')
    bedrooms = db.Column(db.Integer, nullable=True)
    bathrooms = db.Column(db.Integer, nullable=True)
    size_sqm = db.Column(db.String(50), nullable=True)
    features = db.Column(db.Text, nullable=True)
    is_managed = db.Column(db.Boolean, default=False)
    is_published = db.Column(db.Boolean, default=False)
    is_featured = db.Column(db.Boolean, default=False)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    images = db.relationship('PropertyImage', backref='property', lazy=True, cascade='all, delete-orphan')
    user = db.relationship('User', backref='properties', foreign_keys=[user_id])

    @property
    def main_image(self):
        return self.images[0].filename if self.images else None

class PropertyImage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    property_id = db.Column(db.Integer, db.ForeignKey('property.id'))
    filename = db.Column(db.String(255))
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)

class Inquiry(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    visitor_name = db.Column(db.String(100))
    visitor_email = db.Column(db.String(120))
    visitor_phone = db.Column(db.String(30))
    inquiry_type = db.Column(db.String(20), default='property')
    reference_id = db.Column(db.Integer, nullable=True)
    message = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_handled = db.Column(db.Boolean, default=False)
