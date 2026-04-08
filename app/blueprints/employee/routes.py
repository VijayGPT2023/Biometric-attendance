"""Employee routes: dashboard, anomaly report, justification submission."""
import os
import json
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, current_app, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models.attendance import UploadSession
from app.models.justification import Justification
from app.models.audit import AuditLog
from app.blueprints.employee import employee_bp
from app.blueprints.attendance.serializers import deserialize_results
from app.blueprints.attendance.routes import _get_holidays_for_range, _get_holiday_names


@employee_bp.route('/')
@login_required
def dashboard():
    emp_code = current_user.emp_code
    sessions = db.session.query(UploadSession).join(
        Justification, Justification.session_uuid == UploadSession.session_uuid
    ).filter(Justification.emp_code == emp_code).distinct().order_by(
        UploadSession.created_at.desc()).all()

    session_data = []
    for s in sessions:
        justs = Justification.query.filter_by(
            session_uuid=s.session_uuid, emp_code=emp_code
        ).order_by(Justification.anomaly_date).all()

        total = len(justs)
        pending = sum(1 for j in justs if j.status == 'pending')
        submitted = sum(1 for j in justs if j.status == 'submitted')
        query = sum(1 for j in justs if j.status in ('query',))
        accepted = sum(1 for j in justs if j.status == 'accepted')
        declined = sum(1 for j in justs if j.status == 'declined')

        last_sub = max((j.updated_at for j in justs if j.status != 'pending'), default=None)

        session_data.append({
            'session_uuid': s.session_uuid,
            'start_date': s.start_date.isoformat(),
            'end_date': s.end_date.isoformat(),
            'created_at': s.created_at.strftime('%Y-%m-%d %H:%M') if s.created_at else '',
            'total': total, 'pending': pending, 'submitted': submitted,
            'query': query, 'accepted': accepted, 'declined': declined,
            'last_submitted': last_sub.strftime('%Y-%m-%d %H:%M') if last_sub else None,
        })

    return render_template('employee/dashboard.html', session_data=session_data)


@employee_bp.route('/report/<session_uuid>')
@login_required
def report(session_uuid):
    emp_code = current_user.emp_code
    data_path = os.path.join(current_app.config['DATA_FOLDER'], f"{session_uuid}.json")
    if not os.path.exists(data_path):
        flash('Session not found.')
        return redirect(url_for('employee.dashboard'))

    with open(data_path) as f:
        data = json.load(f)
    results, start_date, end_date, params = deserialize_results(data)

    emp_result = next((r for r in results if r['emp_code'] == emp_code), None)
    if not emp_result:
        flash('No attendance data found for your employee code.')
        return redirect(url_for('employee.dashboard'))

    justs = Justification.query.filter_by(
        session_uuid=session_uuid, emp_code=emp_code
    ).order_by(Justification.anomaly_date).all()
    just_map = {j.anomaly_date.isoformat(): {
        'id': j.id, 'justification': j.justification, 'status': j.status,
        'head_remark': j.head_remark,
    } for j in justs}

    upload_session = UploadSession.query.filter_by(session_uuid=session_uuid).first()
    office_id = upload_session.office_id if upload_session else None
    holidays = sorted(_get_holidays_for_range(start_date, end_date, office_id))
    holiday_names = _get_holiday_names(start_date, end_date, office_id)

    return render_template('employee/report.html',
                           emp=emp_result, start_date=start_date,
                           end_date=end_date, params=params,
                           holidays=holidays, holiday_names=holiday_names,
                           session_uuid=session_uuid, just_map=just_map)


@employee_bp.route('/justify/<session_uuid>', methods=['POST'])
@login_required
def justify(session_uuid):
    emp_code = current_user.emp_code
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    count = 0

    for key, value in request.form.items():
        if key.startswith('justification_'):
            anomaly_date = key.replace('justification_', '')
            value = value.strip()
            if value:
                j = Justification.query.filter_by(
                    session_uuid=session_uuid, emp_code=emp_code
                ).filter(
                    db.func.cast(Justification.anomaly_date, db.String) == anomaly_date
                ).first()
                if j and j.status in ('pending', 'query'):
                    j.justification = value
                    j.status = 'submitted'
                    j.updated_at = datetime.utcnow()
                    count += 1

    db.session.commit()
    now_str = datetime.now().strftime('%d-%b-%Y %I:%M %p')

    AuditLog.log('justification_submit', user_id=current_user.id,
                 resource_type='justification', resource_id=session_uuid,
                 details=f'{count} justifications',
                 ip_address=request.headers.get('X-Forwarded-For', request.remote_addr))

    if is_ajax:
        return jsonify({'success': True, 'count': count, 'timestamp': now_str})

    flash(f'Justifications submitted at {now_str}. {count} sent to Head.')
    return redirect(url_for('employee.report', session_uuid=session_uuid))
