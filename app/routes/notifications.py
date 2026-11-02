from datetime import datetime

from flask import Blueprint, abort, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.models import Notification, db

notifications_bp = Blueprint("notifications", __name__, url_prefix="/notifications")


@notifications_bp.route("/")
@login_required
def index():
    items = Notification.query.filter_by(user_id=current_user.id).order_by(
        Notification.created_at.desc()
    ).limit(100).all()
    unread_count = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
    return render_template("notifications/index.html", notifications=items, unread_count=unread_count)


@notifications_bp.route("/<int:notification_id>/open", methods=["POST"])
@login_required
def open_notification(notification_id):
    item = Notification.query.filter_by(id=notification_id, user_id=current_user.id).first_or_404()
    if not item.is_read:
        item.is_read = True
        item.read_at = datetime.utcnow()
        db.session.commit()
    destination = item.target_url or url_for("notifications.index")
    if not destination.startswith("/") or destination.startswith("//"):
        abort(400)
    return redirect(destination)


@notifications_bp.route("/read-all", methods=["POST"])
@login_required
def mark_all_read():
    now = datetime.utcnow()
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update(
        {"is_read": True, "read_at": now},
        synchronize_session=False,
    )
    db.session.commit()
    return redirect(url_for("notifications.index"))
