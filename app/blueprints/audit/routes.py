"""Audit log viewer."""
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.models.audit import AuditLog
from app.models.user import User
from app.blueprints.audit import audit_bp


@audit_bp.route('/')
@login_required
def index():
    if current_user.role not in ('super_admin', 'admin', 'auditor'):
        flash('Access denied.')
        return redirect(url_for('auth.dashboard'))

    page = request.args.get('page', 1, type=int)
    action_filter = request.args.get('action', '')
    user_filter = request.args.get('user_id', type=int)

    query = AuditLog.query
    if action_filter:
        query = query.filter(AuditLog.action == action_filter)
    if user_filter:
        query = query.filter(AuditLog.user_id == user_filter)

    logs = query.order_by(AuditLog.created_at.desc()).paginate(page=page, per_page=50)

    actions = [r[0] for r in AuditLog.query.with_entities(
        AuditLog.action).distinct().order_by(AuditLog.action).all()]

    return render_template('audit/index.html', logs=logs, actions=actions,
                           action_filter=action_filter, user_filter=user_filter)
