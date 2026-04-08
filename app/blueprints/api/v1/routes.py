"""JSON API endpoints for charts, AJAX operations, and data access."""
import os
import json
from flask import jsonify, request, current_app
from flask_login import login_required, current_user
from app.extensions import db
from app.models.attendance import UploadSession
from app.models.justification import Justification
from app.models.notification import Notification
from app.models.holiday import Holiday
from app.models.user import User
from app.blueprints.api.v1 import api_v1_bp
from app.blueprints.attendance.serializers import deserialize_results
from app.utils.helpers import group_by_department


@api_v1_bp.route('/sessions')
@login_required
def sessions():
    """List upload sessions."""
    sessions = UploadSession.query.order_by(UploadSession.created_at.desc()).all()
    return jsonify([{
        'id': s.id, 'uuid': s.session_uuid,
        'start_date': s.start_date.isoformat(),
        'end_date': s.end_date.isoformat(),
        'employee_count': s.employee_count,
        'anomaly_count': s.anomaly_count,
        'status': s.status,
    } for s in sessions])


@api_v1_bp.route('/sessions/<session_uuid>/stats')
@login_required
def session_stats(session_uuid):
    """Get session statistics for charts."""
    data_path = os.path.join(current_app.config['DATA_FOLDER'], f"{session_uuid}.json")
    if not os.path.exists(data_path):
        return jsonify({'error': 'Session not found'}), 404

    with open(data_path) as f:
        data = json.load(f)
    results, start_date, end_date, params = deserialize_results(data)
    dept_groups = group_by_department(results)

    # Department-wise summary for charts
    dept_stats = []
    for dept_name, dept_results in dept_groups.items():
        total_emp = len(dept_results)
        total_anomalies = sum(r['total_anomaly_dates_raw'] for r in dept_results)
        total_leave_ded = sum(r['leave_deduction'] for r in dept_results)
        avg_present_pct = (sum(r['present'] / max(r['working_days'], 1) * 100
                               for r in dept_results) / max(total_emp, 1))
        dept_stats.append({
            'department': dept_name,
            'employees': total_emp,
            'anomalies': total_anomalies,
            'leave_deduction': total_leave_ded,
            'avg_present_pct': round(avg_present_pct, 1),
            'late_count': sum(r['late_arrival_count'] for r in dept_results),
            'early_count': sum(r['early_departure_count'] for r in dept_results),
            'short_hours': sum(r['short_hours_count'] for r in dept_results),
            'absent_count': sum(r['absent'] for r in dept_results),
        })

    # Overall stats
    total = len(results)
    total_working = sum(r['working_days'] for r in results)
    total_present = sum(r['present'] for r in results)
    total_anomalies = sum(r['total_anomaly_dates_raw'] for r in results)

    return jsonify({
        'period': {'start': start_date.isoformat(), 'end': end_date.isoformat()},
        'overview': {
            'total_employees': total,
            'total_working_days': total_working // max(total, 1),
            'total_present': total_present,
            'total_anomalies': total_anomalies,
            'avg_present_pct': round(total_present / max(total_working, 1) * 100, 1),
        },
        'departments': dept_stats,
    })


@api_v1_bp.route('/notifications')
@login_required
def notifications():
    """Get user notifications."""
    notifs = Notification.query.filter_by(
        user_id=current_user.id
    ).order_by(Notification.created_at.desc()).limit(20).all()
    return jsonify([{
        'id': n.id, 'title': n.title, 'message': n.message,
        'type': n.notification_type, 'link': n.link,
        'is_read': n.is_read,
        'created_at': n.created_at.isoformat() if n.created_at else '',
    } for n in notifs])


@api_v1_bp.route('/holidays/<int:year>')
@login_required
def holidays(year):
    """Get holidays for a year."""
    office_id = request.args.get('office_id', type=int)
    query = Holiday.query.filter_by(year=year, is_active=True)
    if office_id:
        query = query.filter(db.or_(Holiday.office_id == office_id, Holiday.office_id == None))
    holidays = query.order_by(Holiday.holiday_date).all()
    return jsonify([{
        'date': h.holiday_date.isoformat(),
        'name': h.name, 'name_hi': h.name_hi,
        'type': h.holiday_type,
    } for h in holidays])


@api_v1_bp.route('/users/search')
@login_required
def user_search():
    """Search users (for autocomplete)."""
    q = request.args.get('q', '').strip()
    if len(q) < 2:
        return jsonify([])
    users = User.query.filter(
        User.is_deleted == False,
        db.or_(
            User.name.ilike(f'%{q}%'),
            User.emp_code.ilike(f'%{q}%'),
            User.username.ilike(f'%{q}%'),
        )
    ).limit(10).all()
    return jsonify([{
        'id': u.id, 'emp_code': u.emp_code,
        'name': u.name, 'username': u.username, 'role': u.role,
    } for u in users])
