from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from app.models import db, User
from app.notifications import notify_new_agent

auth = Blueprint('auth', __name__)

@auth.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name, email, phone, password = request.form.get('name'), request.form.get('email'), request.form.get('phone'), request.form.get('password')
        if not password or len(password) < 6:
            flash('Password must be at least 6 characters.', 'danger'); return redirect(url_for('auth.register'))
        if User.query.filter_by(email=email).first():
            flash('Email already registered. Please login.', 'danger'); return redirect(url_for('auth.login'))
        user = User(name=name, email=email, phone=phone, password=generate_password_hash(password), role='agent', is_approved=False)
        db.session.add(user); db.session.commit(); notify_new_agent(user); login_user(user)
        flash('Registration successful. Upload your payment proof to list properties.', 'success')
        return redirect(url_for('agent.dashboard'))
    return render_template('auth/register.html')

@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = User.query.filter_by(email=request.form.get('email')).first()
        if not user or not check_password_hash(user.password, request.form.get('password', '')):
            flash('Invalid email or password.', 'danger'); return redirect(url_for('auth.login'))
        login_user(user)
        return redirect(url_for('admin_bp.dashboard' if user.role == 'admin' else 'agent.dashboard'))
    return render_template('auth/login.html')

@auth.route('/logout')
@login_required
def logout():
    logout_user(); flash('You have been logged out.', 'info'); return redirect(url_for('public.properties'))
