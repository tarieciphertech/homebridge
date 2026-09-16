from flask import Blueprint, render_template, redirect, url_for, flash, request, send_from_directory
from app.models import db, Property, Inquiry, PlatformSetting
from app.notifications import notify_new_inquiry
import os

public = Blueprint('public', __name__)


def get_student_service_fee():
    setting = PlatformSetting.query.filter_by(key='student_service_fee').first()
    try:
        return float(setting.value) if setting else 0.0
    except (TypeError, ValueError):
        return 0.0


@public.route('/')
def home():
    return redirect(url_for('public.properties'))


@public.route('/properties')
def properties():
    property_type = request.args.get('property_type', '')
    city = request.args.get('city', '')
    rooms = request.args.get('rooms', type=int)
    query = Property.query.filter_by(is_published=True, availability_status='available')
    if property_type:
        query = query.filter_by(property_type=property_type)
    if city:
        query = query.filter(Property.city.ilike(f'%{city}%'))
    if rooms:
        query = query.filter(Property.available_rooms >= rooms)
    all_properties = query.order_by(Property.is_featured.desc(), Property.submitted_at.desc()).all()
    cities = [c[0] for c in db.session.query(Property.city).filter_by(is_published=True).distinct().all() if c[0]]
    return render_template('public/properties.html', properties=all_properties, cities=cities, property_type=property_type, city=city, rooms=rooms or '')


@public.route('/properties/<int:property_id>')
def property_detail(property_id):
    prop = Property.query.filter_by(id=property_id, is_published=True).first_or_404()
    similar = Property.query.filter_by(is_published=True, availability_status='available', city=prop.city).filter(Property.id != prop.id).limit(3).all()
    return render_template('public/property_detail.html', prop=prop, similar=similar, student_service_fee=get_student_service_fee())


@public.route('/inquire', methods=['POST'])
def inquire():
    inquiry = Inquiry(visitor_name=request.form.get('visitor_name'), visitor_email=request.form.get('visitor_email'), visitor_phone=request.form.get('visitor_phone'), inquiry_type='property', reference_id=request.form.get('reference_id', type=int), message=request.form.get('message'))
    db.session.add(inquiry)
    db.session.commit()
    notify_new_inquiry(inquiry, request.form.get('reference_title', 'a property'))
    flash('Your inquiry has been sent. We will contact you shortly.', 'success')
    return redirect(request.referrer or url_for('public.properties'))


@public.route('/uploads/<path:filename>')
def uploaded_file(filename):
    upload_folder = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'static', 'uploads')
    return send_from_directory(upload_folder, filename)
