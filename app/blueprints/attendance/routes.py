"""Attendance upload and analysis routes."""
import os
import json
import uuid
from flask import request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app.extensions import db
from app.models.attendance import UploadSession
from app.models.justification import Justification
from app.models.department import Department
from app.models.holiday import Holiday
from app.models.audit import AuditLog
from app.blueprints.attendance import attendance_bp
from app.blueprints.attendance.parser import parse_biometric_xls, merge_multi_month
from app.blueprints.attendance.analyzer import analyze_employee
from app.blueprints.attendance.serializers import serialize_results


def _get_holidays_for_range(start_date, end_date, office_id=None):
    """Get holidays from database for a date range."""
    query = Holiday.query.filter(
        Holiday.holiday_date >= start_date,
        Holiday.holiday_date <= end_date,
        Holiday.is_active == True
    )
    if office_id:
        query = query.filter(
            db.or_(Holiday.office_id == office_id, Holiday.office_id == None)
        )
    return {h.holiday_date for h in query.all()}


def _get_holiday_names(start_date, end_date, office_id=None):
    query = Holiday.query.filter(
        Holiday.holiday_date >= start_date,
        Holiday.holiday_date <= end_date,
        Holiday.is_active == True
    )
    if office_id:
        query = query.filter(
            db.or_(Holiday.office_id == office_id, Holiday.office_id == None)
        )
    return {h.holiday_date: h.name for h in query.all()}


@attendance_bp.route('/upload', methods=['POST'])
@login_required
def upload():
    """Upload XLS files and run attendance analysis."""
    if current_user.role not in ('super_admin', 'admin'):
        flash('Access denied.')
        return redirect(url_for('auth.dashboard'))

    files = request.files.getlist('files')
    if not files or all(f.filename == '' for f in files):
        flash('No file uploaded')
        return redirect(url_for('admin.dashboard'))

    office_id = request.form.get('office_id', '')
    if not office_id:
        flash('Please select an office.')
        return redirect(url_for('admin.dashboard'))
    office_id = int(office_id)

    try:
        late_h, late_m = map(int, request.form.get('late_time', '10:00').split(':'))
        early_h, early_m = map(int, request.form.get('early_time', '17:00').split(':'))
        min_hours = float(request.form.get('min_hours', '8'))
        allowed_anomalies = int(request.form.get('allowed_anomalies', '2'))
    except (ValueError, TypeError):
        flash('Invalid parameter values')
        return redirect(url_for('admin.dashboard'))

    upload_dir = current_app.config['UPLOAD_FOLDER']
    data_dir = current_app.config['DATA_FOLDER']

    # Parse each uploaded file
    file_results = []
    saved_paths = []
    filenames = []
    for file in files:
        if file.filename == '':
            continue
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in ('.xls', '.xlsx'):
            flash(f'Skipped {file.filename} - not an .xls/.xlsx file')
            continue
        filepath = os.path.join(upload_dir, file.filename)
        file.save(filepath)
        saved_paths.append(filepath)
        filenames.append(file.filename)
        try:
            emps, sd, ed = parse_biometric_xls(filepath)
            if emps and sd and ed:
                file_results.append((emps, sd, ed))
        except Exception as e:
            flash(f'Error parsing {file.filename}: {str(e)}')
            current_app.logger.error(f'Parse error: {file.filename}: {e}', exc_info=True)

    # Cleanup uploaded files
    for fp in saved_paths:
        try:
            os.remove(fp)
        except OSError:
            pass

    if not file_results:
        flash('No valid employee data found in the uploaded file(s)')
        return redirect(url_for('admin.dashboard'))

    # Merge multi-month data
    employees, start_date, end_date = merge_multi_month(file_results)

    params = {
        'late_time': f"{late_h:02d}:{late_m:02d}",
        'early_time': f"{early_h:02d}:{early_m:02d}",
        'min_hours': min_hours,
        'allowed_anomalies': allowed_anomalies,
    }

    # Get holidays from DB
    holidays = _get_holidays_for_range(start_date, end_date, office_id)

    # Analyze each employee
    results = []
    for emp in employees:
        result = analyze_employee(emp, start_date, end_date,
                                  (late_h, late_m), (early_h, early_m),
                                  min_hours, allowed_anomalies,
                                  holidays=holidays)
        results.append(result)

    # Save session data
    session_id = str(uuid.uuid4())
    serialized = serialize_results(results, start_date, end_date, params)
    raw_employees = []
    for emp in employees:
        raw_emp = dict(emp)
        raw_emp['daily_data'] = {d.isoformat(): v for d, v in emp['daily_data'].items()}
        raw_employees.append(raw_emp)
    serialized['raw_employees'] = raw_employees

    data_path = os.path.join(data_dir, f"{session_id}.json")
    with open(data_path, 'w') as f:
        json.dump(serialized, f)

    # Create upload session in DB
    upload_session = UploadSession(
        session_uuid=session_id,
        office_id=office_id,
        uploaded_by=current_user.id,
        start_date=start_date,
        end_date=end_date,
        params_json=json.dumps(params),
        data_file_path=data_path,
        status='active',
        employee_count=len(results),
        anomaly_count=sum(r['total_anomaly_dates_raw'] for r in results),
        original_filenames=', '.join(filenames),
    )
    db.session.add(upload_session)
    db.session.commit()

    # Auto-create departments
    from app.utils.helpers import group_by_department
    dept_groups = group_by_department(results)
    for dept_name in dept_groups:
        existing = Department.query.filter_by(name=dept_name, office_id=office_id).first()
        if not existing:
            db.session.add(Department(name=dept_name, office_id=office_id))
    db.session.commit()

    # Populate justification rows
    for r in results:
        for detail in r.get('anomaly_details', []):
            d = detail['date']
            date_str = d.isoformat() if hasattr(d, 'isoformat') else d
            types_str = ', '.join(detail.get('types', []))
            existing = Justification.query.filter_by(
                session_uuid=session_id, emp_code=r['emp_code'],
                anomaly_date=d if hasattr(d, 'isoformat') else None
            ).first()
            if not existing:
                db.session.add(Justification(
                    session_id=upload_session.id,
                    session_uuid=session_id,
                    emp_code=r['emp_code'],
                    anomaly_date=d,
                    anomaly_types=types_str,
                    status='pending',
                ))
    db.session.commit()

    AuditLog.log('upload_xls', user_id=current_user.id,
                 resource_type='upload_session', resource_id=session_id,
                 details=f'{len(results)} employees, {len(filenames)} files',
                 ip_address=request.headers.get('X-Forwarded-For', request.remote_addr))

    flash(f'Analysis complete! {len(results)} employees, '
          f'{sum(r["total_anomaly_dates_raw"] for r in results)} anomalies detected.')
    return redirect(url_for('admin.dashboard'))
