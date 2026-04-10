"""Admin routes: dashboard, user management, office/dept CRUD, review, finalize."""
import json
import os
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from werkzeug.security import generate_password_hash
from app.extensions import db
from app.models.user import User
from app.models.office import Office
from app.models.department import Department
from app.models.attendance import UploadSession
from app.models.justification import Justification
from app.models.audit import AuditLog
from app.utils.helpers import generate_username, group_by_department
from app.blueprints.admin import admin_bp
from app.blueprints.attendance.serializers import deserialize_results


def _admin_required(f):
    from functools import wraps
    @wraps(f)
    @login_required
    def decorated(*args, **kwargs):
        if current_user.role not in ('super_admin', 'admin'):
            flash('Access denied.')
            return redirect(url_for('auth.dashboard'))
        return f(*args, **kwargs)
    return decorated


@admin_bp.route('/')
@_admin_required
def dashboard():
    sessions = UploadSession.query.order_by(UploadSession.created_at.desc()).all()
    users = User.query.filter_by(is_deleted=False).order_by(User.role, User.name).all()
    departments = Department.query.order_by(Department.name).all()
    offices = Office.query.order_by(Office.name).all()
    return render_template('admin/dashboard.html',
                           sessions=sessions, users=users,
                           departments=departments, offices=offices)


@admin_bp.route('/users')
@_admin_required
def users():
    all_users = User.query.filter_by(is_deleted=False).order_by(User.role, User.name).all()
    departments = Department.query.order_by(Department.name).all()
    offices = Office.query.order_by(Office.name).all()
    head_depts = {}
    for u in all_users:
        if u.role == 'head':
            head_depts[u.id] = [d.name for d in u.head_departments]
    return render_template('admin/users.html',
                           users=all_users, departments=departments,
                           offices=offices, head_depts=head_depts)


@admin_bp.route('/users/add', methods=['POST'])
@_admin_required
def add_user():
    emp_code = request.form.get('emp_code', '').strip()
    name = request.form.get('name', '').strip()
    password = request.form.get('password', '').strip()
    role = request.form.get('role', 'employee')
    office_id = request.form.get('office_id', type=int)
    dept_ids = request.form.getlist('departments')

    if not emp_code or not name or not password:
        flash('All fields are required.')
        return redirect(url_for('admin.users'))

    existing_usernames = {u.username for u in User.query.all()}
    username = generate_username(name, existing_usernames)

    user = User(
        emp_code=emp_code, name=name, username=username,
        role=role, office_id=office_id, must_change_password=True
    )
    user.set_password(password)
    db.session.add(user)
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash(f'Employee code "{emp_code}" already exists.')
        return redirect(url_for('admin.users'))

    if role == 'head' and dept_ids:
        for did in dept_ids:
            dept = Department.query.get(int(did))
            if dept:
                user.head_departments.append(dept)
        db.session.commit()

    AuditLog.log('user_create', user_id=current_user.id,
                 resource_type='user', resource_id=str(user.id),
                 details=f'{name} ({role})',
                 ip_address=request.headers.get('X-Forwarded-For', request.remote_addr))
    flash(f'User {name} added. Username: {username}')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/edit', methods=['POST'])
@_admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    user.name = request.form.get('name', user.name).strip()
    user.role = request.form.get('role', user.role)
    user.is_active = bool(request.form.get('is_active'))
    user.office_id = request.form.get('office_id', type=int) or user.office_id

    password = request.form.get('password', '').strip()
    if password:
        user.set_password(password)
        user.must_change_password = True

    dept_ids = request.form.getlist('departments')
    user.head_departments = []
    if user.role == 'head' and dept_ids:
        for did in dept_ids:
            dept = Department.query.get(int(did))
            if dept:
                user.head_departments.append(dept)

    db.session.commit()
    AuditLog.log('user_edit', user_id=current_user.id,
                 resource_type='user', resource_id=str(user_id))
    flash('User updated.')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/reset-password', methods=['POST'])
@_admin_required
def reset_password(user_id):
    user = User.query.get_or_404(user_id)
    default_pw = 'npc123'
    user.set_password(default_pw)
    user.must_change_password = True
    user.active_session_id = ''
    user.last_activity = None
    user.failed_login_count = 0
    user.locked_until = None
    db.session.commit()
    AuditLog.log('password_reset', user_id=current_user.id,
                 resource_type='user', resource_id=str(user_id))
    flash(f'Password reset for {user.name}. New password: {default_pw}')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@_admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.emp_code == 'admin':
        flash('Cannot delete admin user.')
        return redirect(url_for('admin.users'))
    user.is_deleted = True
    user.deleted_at = datetime.utcnow()
    user.is_active = False
    db.session.commit()
    AuditLog.log('user_delete', user_id=current_user.id,
                 resource_type='user', resource_id=str(user_id))
    flash('User deleted.')
    return redirect(url_for('admin.users'))


@admin_bp.route('/offices/add', methods=['POST'])
@_admin_required
def add_office():
    name = request.form.get('office_name', '').strip()
    code = request.form.get('office_code', '').strip().upper()
    location = request.form.get('office_location', '').strip()
    if name and code:
        office = Office(name=name, code=code, location=location)
        db.session.add(office)
        try:
            db.session.commit()
            AuditLog.log('office_create', user_id=current_user.id,
                         resource_type='office', resource_id=str(office.id))
            flash(f'Office "{name}" ({code}) added.')
        except Exception:
            db.session.rollback()
            flash(f'Office "{name}" or code "{code}" already exists.')
    return redirect(url_for('admin.users'))


@admin_bp.route('/departments/add', methods=['POST'])
@_admin_required
def add_department():
    name = request.form.get('dept_name', '').strip()
    office_id = request.form.get('office_id', type=int)
    if name:
        dept = Department(name=name, office_id=office_id)
        db.session.add(dept)
        try:
            db.session.commit()
            AuditLog.log('department_create', user_id=current_user.id,
                         resource_type='department', resource_id=str(dept.id))
            flash(f'Department "{name}" added.')
        except Exception:
            db.session.rollback()
            flash(f'Department "{name}" already exists.')
    return redirect(url_for('admin.users'))


@admin_bp.route('/review/<session_uuid>')
@_admin_required
def review(session_uuid):
    upload_session = UploadSession.query.filter_by(session_uuid=session_uuid).first_or_404()
    data_path = upload_session.data_file_path
    if not data_path or not os.path.exists(data_path):
        data_path = os.path.join(current_app.config['DATA_FOLDER'], f"{session_uuid}.json")
    if not os.path.exists(data_path):
        flash('Session data not found.')
        return redirect(url_for('admin.dashboard'))

    with open(data_path) as f:
        data = json.load(f)
    results, start_date, end_date, params = deserialize_results(data)
    dept_groups = group_by_department(results)

    justifications = Justification.query.filter_by(session_uuid=session_uuid).order_by(
        Justification.emp_code, Justification.anomaly_date).all()
    just_map = {}
    for j in justifications:
        just_map.setdefault(j.emp_code, {})[j.anomaly_date.isoformat()] = {
            'id': j.id, 'justification': j.justification, 'status': j.status,
            'head_remark': j.head_remark, 'admin_remark': j.admin_remark,
            'finalized': j.finalized, 'final_decision': j.final_decision,
        }

    return render_template('admin/review.html',
                           dept_groups=dept_groups, results=results,
                           start_date=start_date, end_date=end_date,
                           params=params, session_uuid=session_uuid,
                           just_map=just_map)


@admin_bp.route('/finalize/<session_uuid>', methods=['POST'])
@_admin_required
def finalize(session_uuid):
    for key, value in request.form.items():
        if key.startswith('decision_'):
            parts = key.split('_', 2)
            if len(parts) == 3:
                emp_code, anomaly_date = parts[1], parts[2]
                admin_remark = request.form.get(f'admin_remark_{emp_code}_{anomaly_date}', '')
                j = Justification.query.filter_by(
                    session_uuid=session_uuid, emp_code=emp_code,
                ).filter(db.func.cast(Justification.anomaly_date, db.String) == anomaly_date).first()
                if j:
                    j.finalized = True
                    j.final_decision = value
                    j.admin_remark = admin_remark
                    j.admin_reviewed_by = current_user.id
                    j.admin_reviewed_at = datetime.utcnow()
    db.session.commit()
    AuditLog.log('finalize', user_id=current_user.id,
                 resource_type='upload_session', resource_id=session_uuid)
    flash('Decisions finalized.')
    return redirect(url_for('admin.review', session_uuid=session_uuid))


@admin_bp.route('/sessions/<session_uuid>/delete', methods=['POST'])
@_admin_required
def delete_session(session_uuid):
    """Delete an upload session and all its data."""
    upload_session = UploadSession.query.filter_by(session_uuid=session_uuid).first()
    if not upload_session:
        flash('Session not found.')
        return redirect(url_for('admin.dashboard'))

    # Delete justifications
    Justification.query.filter_by(session_uuid=session_uuid).delete()
    # Delete JSON data file
    data_path = os.path.join(current_app.config['DATA_FOLDER'], f"{session_uuid}.json")
    try:
        os.remove(data_path)
    except OSError:
        pass
    # Delete session record
    db.session.delete(upload_session)
    db.session.commit()

    AuditLog.log('session_delete', user_id=current_user.id,
                 resource_type='upload_session', resource_id=session_uuid,
                 ip_address=request.headers.get('X-Forwarded-For', request.remote_addr))
    flash(f'Session {upload_session.start_date} to {upload_session.end_date} deleted.')
    return redirect(url_for('admin.dashboard'))


@admin_bp.route('/data-management')
@_admin_required
def data_management():
    """Admin data management page: sessions, bulk operations."""
    sessions = UploadSession.query.order_by(UploadSession.created_at.desc()).all()
    users = User.query.filter_by(is_deleted=False).order_by(User.name).all()
    offices = Office.query.order_by(Office.name).all()
    return render_template('admin/data_management.html',
                           sessions=sessions, users=users, offices=offices)


@admin_bp.route('/report/<session_uuid>')
@_admin_required
def report(session_uuid):
    data_path = os.path.join(current_app.config['DATA_FOLDER'], f"{session_uuid}.json")
    if not os.path.exists(data_path):
        flash('Session not found.')
        return redirect(url_for('admin.dashboard'))

    with open(data_path) as f:
        data = json.load(f)
    results, start_date, end_date, params = deserialize_results(data)

    # Apply finalized exclusions
    for r in results:
        excluded = Justification.query.filter_by(
            session_uuid=session_uuid, emp_code=r['emp_code'],
            finalized=True, final_decision='excluded'
        ).all()
        excluded_dates = {j.anomaly_date for j in excluded}
        if excluded_dates:
            r['permitted_dates'] = sorted(excluded_dates & set(r['all_anomaly_dates']))
            r['permitted_count'] = len(r['permitted_dates'])
            effective = set(r['all_anomaly_dates']) - excluded_dates
            r['effective_anomaly_count'] = len(effective)
            r['effective_anomaly_dates'] = sorted(effective)
            r['leave_deduction'] = max(0, (len(effective) - r['allowed_anomalies']) * 0.5)

    from app.blueprints.attendance.routes import _get_holidays_for_range, _get_holiday_names
    upload_session = UploadSession.query.filter_by(session_uuid=session_uuid).first()
    office_id = upload_session.office_id if upload_session else None
    holidays = sorted(_get_holidays_for_range(start_date, end_date, office_id))
    holiday_names = _get_holiday_names(start_date, end_date, office_id)
    dept_groups = group_by_department(results)

    return render_template('admin/report.html',
                           dept_groups=dept_groups, results=results,
                           start_date=start_date, end_date=end_date,
                           params=params, holidays=holidays,
                           holiday_names=holiday_names,
                           session_id=session_uuid, stage='final')
