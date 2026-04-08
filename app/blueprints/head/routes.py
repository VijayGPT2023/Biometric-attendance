"""Head routes: dashboard, employee detail, review, submit decisions."""
import os
import json
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app.extensions import db
from app.models.department import Department
from app.models.attendance import UploadSession
from app.models.justification import Justification
from app.models.audit import AuditLog
from app.blueprints.head import head_bp
from app.blueprints.attendance.serializers import deserialize_results
from app.blueprints.attendance.routes import _get_holidays_for_range, _get_holiday_names
from app.utils.helpers import group_by_department


def _get_managed_depts():
    """Get department names managed by current user."""
    if current_user.role in ('super_admin', 'admin'):
        return [d.name for d in Department.query.order_by(Department.name).all()]
    return [d.name for d in current_user.head_departments]


@head_bp.route('/')
@login_required
def dashboard():
    if current_user.role not in ('super_admin', 'admin', 'head'):
        flash('Access denied.')
        return redirect(url_for('auth.dashboard'))

    managed_depts = _get_managed_depts()
    if not managed_depts:
        flash('No departments assigned to you.')
        return render_template('head/dashboard.html',
                               managed_depts=[], dept_groups={},
                               session_uuid=None, start_date=None, end_date=None,
                               params=None, just_summary={}, active_dept='')

    active_dept = request.args.get('dept', '')
    if active_dept and active_dept not in managed_depts:
        active_dept = ''

    latest = UploadSession.query.order_by(UploadSession.created_at.desc()).first()
    empty_ctx = dict(managed_depts=managed_depts, dept_groups={},
                     session_uuid=None, start_date=None, end_date=None,
                     params=None, just_summary={}, active_dept=active_dept)

    if not latest:
        return render_template('head/dashboard.html', **empty_ctx)

    data_path = os.path.join(current_app.config['DATA_FOLDER'], f"{latest.session_uuid}.json")
    if not os.path.exists(data_path):
        return render_template('head/dashboard.html', **empty_ctx)

    with open(data_path) as f:
        data = json.load(f)
    results, start_date, end_date, params = deserialize_results(data)

    # Filter by department
    show_depts = managed_depts
    if len(managed_depts) > 3:
        if active_dept:
            show_depts = [active_dept]
        else:
            return render_template('head/dashboard.html',
                                   managed_depts=managed_depts, dept_groups={},
                                   session_uuid=latest.session_uuid,
                                   start_date=start_date, end_date=end_date,
                                   params=params, just_summary={},
                                   active_dept=active_dept, pick_dept=True)

    dept_results = [r for r in results if r['department'] in show_depts]
    dept_groups = group_by_department(dept_results)

    # Get justification summary
    emp_codes = [r['emp_code'] for r in dept_results]
    just_summary = {}
    if emp_codes:
        justs = Justification.query.filter(
            Justification.session_uuid == latest.session_uuid,
            Justification.emp_code.in_(emp_codes)
        ).all()
        for j in justs:
            if j.emp_code not in just_summary:
                just_summary[j.emp_code] = {'pending': 0, 'submitted': 0,
                                             'query': 0, 'accepted': 0, 'declined': 0}
            st = j.status
            if st in just_summary[j.emp_code]:
                just_summary[j.emp_code][st] += 1
            elif st == 'resubmitted':
                just_summary[j.emp_code]['submitted'] += 1

    return render_template('head/dashboard.html',
                           managed_depts=managed_depts, dept_groups=dept_groups,
                           session_uuid=latest.session_uuid,
                           start_date=start_date, end_date=end_date,
                           params=params, just_summary=just_summary,
                           active_dept=active_dept)


@head_bp.route('/employee/<session_uuid>/<emp_code>')
@login_required
def employee_detail(session_uuid, emp_code):
    if current_user.role not in ('super_admin', 'admin', 'head'):
        flash('Access denied.')
        return redirect(url_for('auth.dashboard'))

    data_path = os.path.join(current_app.config['DATA_FOLDER'], f"{session_uuid}.json")
    if not os.path.exists(data_path):
        flash('Session not found.')
        return redirect(url_for('head.dashboard'))

    with open(data_path) as f:
        data = json.load(f)
    results, start_date, end_date, params = deserialize_results(data)

    emp_result = next((r for r in results if r['emp_code'] == emp_code), None)
    if not emp_result:
        flash('Employee not found.')
        return redirect(url_for('head.dashboard'))

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

    return render_template('head/employee_detail.html',
                           emp=emp_result, start_date=start_date,
                           end_date=end_date, params=params,
                           holidays=holidays, holiday_names=holiday_names,
                           session_uuid=session_uuid, just_map=just_map)


@head_bp.route('/review/<session_uuid>')
@login_required
def review(session_uuid):
    if current_user.role not in ('super_admin', 'admin', 'head'):
        flash('Access denied.')
        return redirect(url_for('auth.dashboard'))

    managed_depts = _get_managed_depts()
    data_path = os.path.join(current_app.config['DATA_FOLDER'], f"{session_uuid}.json")
    if not os.path.exists(data_path):
        flash('Session not found.')
        return redirect(url_for('head.dashboard'))

    with open(data_path) as f:
        data = json.load(f)
    results, start_date, end_date, params = deserialize_results(data)
    dept_results = [r for r in results if r['department'] in managed_depts]
    dept_groups = group_by_department(dept_results)

    emp_codes = [r['emp_code'] for r in dept_results]
    just_map = {}
    if emp_codes:
        justs = Justification.query.filter(
            Justification.session_uuid == session_uuid,
            Justification.emp_code.in_(emp_codes)
        ).order_by(Justification.emp_code, Justification.anomaly_date).all()
        for j in justs:
            just_map.setdefault(j.emp_code, {})[j.anomaly_date.isoformat()] = {
                'id': j.id, 'justification': j.justification, 'status': j.status,
                'head_remark': j.head_remark,
            }

    upload_session = UploadSession.query.filter_by(session_uuid=session_uuid).first()
    office_id = upload_session.office_id if upload_session else None
    holidays = sorted(_get_holidays_for_range(start_date, end_date, office_id))
    holiday_names = _get_holiday_names(start_date, end_date, office_id)

    return render_template('head/review.html',
                           dept_groups=dept_groups, results=dept_results,
                           start_date=start_date, end_date=end_date,
                           params=params, session_uuid=session_uuid,
                           just_map=just_map, holidays=holidays,
                           holiday_names=holiday_names)


@head_bp.route('/submit/<session_uuid>', methods=['POST'])
@login_required
def submit(session_uuid):
    if current_user.role not in ('super_admin', 'admin', 'head'):
        flash('Access denied.')
        return redirect(url_for('auth.dashboard'))

    for key, value in request.form.items():
        if key.startswith('action_'):
            parts = key.split('_', 2)
            if len(parts) == 3:
                emp_code, anomaly_date = parts[1], parts[2]
                head_remark = request.form.get(f'remark_{emp_code}_{anomaly_date}', '')
                j = Justification.query.filter_by(
                    session_uuid=session_uuid, emp_code=emp_code,
                ).filter(
                    db.func.cast(Justification.anomaly_date, db.String) == anomaly_date
                ).first()
                if j and j.status in ('submitted', 'resubmitted', 'query'):
                    j.status = value  # accepted, declined, query
                    j.head_remark = head_remark
                    j.head_reviewed_by = current_user.id
                    j.head_reviewed_at = datetime.utcnow()

    db.session.commit()
    AuditLog.log('justification_review', user_id=current_user.id,
                 resource_type='upload_session', resource_id=session_uuid,
                 ip_address=request.headers.get('X-Forwarded-For', request.remote_addr))
    flash('Decisions submitted.')
    return redirect(url_for('head.review', session_uuid=session_uuid))
