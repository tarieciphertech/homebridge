from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash, generate_password_hash
from app.models import db, User, Payment, Property, PropertyImage, Inquiry
from app.notifications import notify_user_activated
from datetime import datetime
import os

admin_bp = Blueprint('admin_bp', __name__, url_prefix='/admin')

def admin_required(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Admin access required.', 'danger'); return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated

def save_file(file, subfolder):
    filename = secure_filename(file.filename); folder = os.path.join(current_app.config['UPLOAD_FOLDER'], subfolder); os.makedirs(folder, exist_ok=True); file.save(os.path.join(folder, filename)); return os.path.join(subfolder, filename)

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    stats = {'total_properties': Property.query.filter_by(is_published=True).count(), 'pending_payments': Payment.query.filter_by(status='pending').count(), 'total_agents': User.query.filter_by(role='agent').count(), 'pending_properties': Property.query.filter_by(is_published=False).count(), 'new_inquiries': Inquiry.query.filter_by(is_handled=False).count()}
    recent_inquiries = Inquiry.query.filter_by(is_handled=False).order_by(Inquiry.submitted_at.desc()).limit(5).all()
    return render_template('admin/dashboard.html', stats=stats, recent_inquiries=recent_inquiries)

@admin_bp.route('/payments')
@login_required
@admin_required
def payments(): return render_template('admin/payments.html', payments=Payment.query.order_by(Payment.submitted_at.desc()).all())

@admin_bp.route('/confirm-payment/<int:payment_id>')
@login_required
@admin_required
def confirm_payment(payment_id):
    payment = Payment.query.get_or_404(payment_id); payment.status='confirmed'; payment.confirmed_at=datetime.utcnow(); user=User.query.get(payment.user_id); user.is_approved=True; db.session.commit(); notify_user_activated(user); flash('Payment confirmed and account activated.', 'success'); return redirect(url_for('admin_bp.payments'))

@admin_bp.route('/reject-payment/<int:payment_id>')
@login_required
@admin_required
def reject_payment(payment_id):
    payment=Payment.query.get_or_404(payment_id); payment.status='rejected'; db.session.commit(); flash('Payment rejected.', 'warning'); return redirect(url_for('admin_bp.payments'))

@admin_bp.route('/properties')
@login_required
@admin_required
def properties(): return render_template('admin/properties.html', properties=Property.query.order_by(Property.submitted_at.desc()).all())

@admin_bp.route('/publish-property/<int:property_id>')
@login_required
@admin_required
def publish_property(property_id):
    prop=Property.query.get_or_404(property_id); prop.is_published=not prop.is_published; db.session.commit(); flash(f'Property {"published" if prop.is_published else "unpublished"}.', 'success'); return redirect(url_for('admin_bp.properties'))

@admin_bp.route('/feature-property/<int:property_id>')
@login_required
@admin_required
def feature_property(property_id):
    prop=Property.query.get_or_404(property_id); prop.is_featured=not prop.is_featured; db.session.commit(); return redirect(url_for('admin_bp.properties'))

@admin_bp.route('/add-property', methods=['GET','POST'])
@login_required
@admin_required
def add_property():
    if request.method == 'POST':
        prop=Property(user_id=current_user.id, title=request.form.get('title'), description=request.form.get('description'), property_type=request.form.get('property_type'), listing_type=request.form.get('listing_type'), price=request.form.get('price'), location=request.form.get('location'), city=request.form.get('city'), country=request.form.get('country','Zimbabwe'), bedrooms=request.form.get('bedrooms') or None, bathrooms=request.form.get('bathrooms') or None, size_sqm=request.form.get('size_sqm'), features=request.form.get('features'), is_managed=request.form.get('is_managed')=='on', is_published=True, is_featured=request.form.get('is_featured')=='on')
        db.session.add(prop); db.session.flush()
        for img in request.files.getlist('images'):
            if img and img.filename: db.session.add(PropertyImage(property_id=prop.id, filename=save_file(img,'properties')))
        db.session.commit(); flash('Property added and published.', 'success'); return redirect(url_for('admin_bp.properties'))
    return render_template('admin/add_property.html')

@admin_bp.route('/inquiries')
@login_required
@admin_required
def inquiries(): return render_template('admin/inquiries.html', inquiries=Inquiry.query.order_by(Inquiry.submitted_at.desc()).all())

@admin_bp.route('/handle-inquiry/<int:inquiry_id>')
@login_required
@admin_required
def handle_inquiry(inquiry_id):
    inquiry=Inquiry.query.get_or_404(inquiry_id); inquiry.is_handled=True; db.session.commit(); return redirect(url_for('admin_bp.inquiries'))

@admin_bp.route('/change-password', methods=['POST'])
@login_required
@admin_required
def change_password():
    current_password=request.form.get('current_password'); new_password=request.form.get('new_password'); confirm=request.form.get('confirm_password')
    if not check_password_hash(current_user.password,current_password): flash('Current password incorrect.','danger')
    elif new_password != confirm: flash('New passwords do not match.','danger')
    elif len(new_password)<6: flash('Password must be at least 6 characters.','danger')
    else: current_user.password=generate_password_hash(new_password); db.session.commit(); flash('Password updated.','success')
    return redirect(url_for('admin_bp.dashboard'))
