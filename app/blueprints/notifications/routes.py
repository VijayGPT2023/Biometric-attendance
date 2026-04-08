"""In-app notifications."""
from flask import render_template, jsonify, request
from flask_login import login_required, current_user
from app.extensions import db
from app.models.notification import Notification
from app.blueprints.notifications import notifications_bp


@notifications_bp.route('/')
@login_required
def index():
    page = request.args.get('page', 1, type=int)
    notifications = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).paginate(page=page, per_page=20)
    return render_template('notifications/index.html', notifications=notifications)


@notifications_bp.route('/unread-count')
@login_required
def unread_count():
    count = Notification.query.filter_by(
        user_id=current_user.id, is_read=False).count()
    return jsonify({'count': count})


@notifications_bp.route('/<int:notif_id>/read', methods=['POST'])
@login_required
def mark_read(notif_id):
    n = Notification.query.filter_by(id=notif_id, user_id=current_user.id).first_or_404()
    n.is_read = True
    db.session.commit()
    return jsonify({'success': True})


@notifications_bp.route('/mark-all-read', methods=['POST'])
@login_required
def mark_all_read():
    Notification.query.filter_by(
        user_id=current_user.id, is_read=False
    ).update({'is_read': True})
    db.session.commit()
    return jsonify({'success': True})
