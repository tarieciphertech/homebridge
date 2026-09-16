from flask import current_app
from flask_mail import Message


def notify_admin(subject, body):
    try:
        from app import mail
        mail.send(Message(subject=f"[HomeBridge] {subject}", recipients=[current_app.config["ADMIN_EMAIL"]], body=body))
    except Exception as exc:
        print(f"Email error: {exc}")


def notify_new_landlord(user):
    notify_admin("New Landlord Registered", f"Name: {user.name}\nEmail: {user.email}\nPhone: {user.phone or ''}")


def notify_payment_uploaded(user, amount, payment_type="platform payment"):
    notify_admin("Payment Proof Uploaded", f"Name: {user.name}\nEmail: {user.email}\nPhone: {user.phone or ''}\nType: {payment_type}\nAmount: {amount}")


def notify_property_submitted(user, prop):
    notify_admin("New Property Submitted", f"Landlord: {user.name}\nTitle: {prop.title}\nType: {prop.listing_type}\nLocation: {prop.location}\nPrice: {prop.price}")


def notify_new_inquiry(inquiry, reference):
    notify_admin(f"New Inquiry — {reference}", f"From: {inquiry.visitor_name}\nEmail: {inquiry.visitor_email}\nPhone: {inquiry.visitor_phone}\nRe: {reference}\n\n{inquiry.message}")


def notify_user_activated(user):
    try:
        from app import mail
        mail.send(Message(subject="Your HomeBridge Landlord Account is Active", recipients=[user.email], body=f"Hi {user.name},\n\nYour landlord account has been approved and you can now submit property listings."))
    except Exception as exc:
        print(f"Email error: {exc}")
