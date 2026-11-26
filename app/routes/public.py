from flask import Blueprint, abort, render_template, redirect, url_for, flash, request, send_from_directory
from sqlalchemy import or_
from app.models import db, Property, Inquiry, PlatformSetting, PropertyLocalDetails
from app.notifications import notify_new_inquiry
from pathlib import PurePosixPath
import os

public = Blueprint("public", __name__)


def get_student_service_fee():
    setting = PlatformSetting.query.filter_by(key="student_service_fee").first()
    try:
        return float(setting.value) if setting else 0.0
    except (TypeError, ValueError):
        return 0.0


@public.route("/")
def home():
    return redirect(url_for("public.properties"))


@public.route("/properties")
def properties():
    property_type = request.args.get("property_type", "").strip()
    city = request.args.get("city", "").strip()
    rooms = request.args.get("rooms", type=int)
    # Keep accepting the old institution parameter for bookmarked student searches.
    keyword = (request.args.get("q") or request.args.get("institution") or "").strip()
    min_price = request.args.get("min_price", type=float)
    max_price = request.args.get("max_price", type=float)
    rent_period = request.args.get("rent_period", "").strip()

    query = Property.query.filter_by(is_published=True, availability_status="available")
    if property_type:
        query = query.filter_by(property_type=property_type)
    if city:
        query = query.filter(Property.city.ilike(f"%{city}%"))
    if rooms:
        query = query.filter(Property.available_rooms >= rooms)
    if min_price is not None and min_price >= 0:
        query = query.filter(Property.price >= min_price)
    if max_price is not None and max_price >= 0:
        query = query.filter(Property.price <= max_price)
    if rent_period:
        query = query.outerjoin(PropertyLocalDetails)
        if rent_period == "month":
            # Existing listings without local detail rows display as monthly by default.
            query = query.filter(or_(PropertyLocalDetails.rent_period == "month", PropertyLocalDetails.id.is_(None)))
        else:
            query = query.filter(PropertyLocalDetails.rent_period == rent_period)
    if keyword:
        if not rent_period:
            query = query.outerjoin(PropertyLocalDetails)
        pattern = f"%{keyword}%"
        query = query.filter(or_(
            Property.title.ilike(pattern),
            Property.description.ilike(pattern),
            Property.location.ilike(pattern),
            Property.city.ilike(pattern),
            Property.country.ilike(pattern),
            Property.property_type.ilike(pattern),
            PropertyLocalDetails.institution_name.ilike(pattern),
            PropertyLocalDetails.campus_name.ilike(pattern),
        )).distinct()

    all_properties = query.order_by(Property.is_featured.desc(), Property.submitted_at.desc()).all()
    cities = [c[0] for c in db.session.query(Property.city).filter_by(is_published=True).distinct().all() if c[0]]
    return render_template(
        "public/properties.html",
        properties=all_properties,
        cities=cities,
        property_type=property_type,
        city=city,
        rooms=rooms or "",
        institution=keyword,
        keyword=keyword,
        min_price="" if min_price is None else min_price,
        max_price="" if max_price is None else max_price,
        rent_period=rent_period,
    )

@public.route("/properties/<int:property_id>")
def property_detail(property_id):
    prop = Property.query.filter_by(id=property_id, is_published=True).first_or_404()
    similar = Property.query.filter_by(
        is_published=True, availability_status="available", city=prop.city
    ).filter(Property.id != prop.id).limit(3).all()
    return render_template(
        "public/property_detail.html",
        prop=prop,
        similar=similar,
        student_service_fee=get_student_service_fee(),
    )


@public.route("/inquire", methods=["POST"])
def inquire():
    inquiry = Inquiry(
        visitor_name=request.form.get("visitor_name"),
        visitor_email=request.form.get("visitor_email"),
        visitor_phone=request.form.get("visitor_phone"),
        inquiry_type="property",
        reference_id=request.form.get("reference_id", type=int),
        message=request.form.get("message"),
    )
    db.session.add(inquiry)
    db.session.commit()
    notify_new_inquiry(inquiry, request.form.get("reference_title", "a property"))
    flash("Your inquiry has been sent. We will contact you shortly.", "success")
    return redirect(request.referrer or url_for("public.properties"))


@public.route("/uploads/<path:filename>")
def uploaded_file(filename):
    # Only property photographs are public. Payment receipts and other uploads
    # must be retrieved through authenticated, ownership-checked download routes.
    safe_path = PurePosixPath(filename)
    if safe_path.is_absolute() or ".." in safe_path.parts or not safe_path.parts:
        abort(404)
    if safe_path.parts[0] != "properties":
        abort(404)

    upload_folder = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "static",
        "uploads",
    )
    return send_from_directory(upload_folder, str(safe_path))
