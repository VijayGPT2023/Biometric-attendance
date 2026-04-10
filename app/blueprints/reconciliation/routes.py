"""eHRMS Leave Reconciliation: upload leave data, match with biometric absence."""
import os
import uuid
from datetime import date, timedelta
from flask import render_template, request, redirect, url_for, flash, current_app
from flask_login import login_required, current_user
from app.extensions import db
from app.models.attendance import UploadSession, AttendanceRecord
from app.models.reconciliation import EHRMSLeaveRecord, ReconciliationResult
from app.models.audit import AuditLog
from app.blueprints.reconciliation import reconciliation_bp
from app.blueprints.attendance.serializers import deserialize_results
import json
import pandas as pd


@reconciliation_bp.route('/')
@login_required
def dashboard():
    if current_user.role not in ('super_admin', 'admin'):
        flash('Access denied.')
        return redirect(url_for('auth.dashboard'))

    sessions = UploadSession.query.order_by(UploadSession.created_at.desc()).all()
    batches = db.session.query(
        EHRMSLeaveRecord.upload_batch_id,
        db.func.count(EHRMSLeaveRecord.id).label('count'),
        db.func.min(EHRMSLeaveRecord.created_at).label('uploaded_at')
    ).group_by(EHRMSLeaveRecord.upload_batch_id).order_by(
        db.func.min(EHRMSLeaveRecord.created_at).desc()).all()

    # Get reconciliation results summary
    recon_summary = {}
    for batch in batches:
        flags = db.session.query(
            ReconciliationResult.flag, db.func.count(ReconciliationResult.id)
        ).filter_by(batch_id=batch.upload_batch_id).group_by(
            ReconciliationResult.flag).all()
        recon_summary[batch.upload_batch_id] = dict(flags)

    return render_template('reconciliation/dashboard.html',
                           sessions=sessions, batches=batches,
                           recon_summary=recon_summary)


@reconciliation_bp.route('/upload', methods=['POST'])
@login_required
def upload_ehrms():
    """Upload eHRMS leave data CSV/Excel and run reconciliation."""
    if current_user.role not in ('super_admin', 'admin'):
        flash('Access denied.')
        return redirect(url_for('auth.dashboard'))

    file = request.files.get('ehrms_file')
    session_uuid = request.form.get('session_uuid', '')
    office_id = request.form.get('office_id', type=int)

    if not file or not session_uuid:
        flash('Please select a file and attendance session.')
        return redirect(url_for('reconciliation.dashboard'))

    # Parse the eHRMS file
    ext = os.path.splitext(file.filename)[1].lower()
    try:
        if ext == '.csv':
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
    except Exception as e:
        flash(f'Error reading file: {e}')
        return redirect(url_for('reconciliation.dashboard'))

    # Support both eHRMS format and generic format
    df.columns = [c.strip() for c in df.columns]

    # Detect eHRMS format (has 'Email' and 'From Date' columns)
    is_ehrms = 'Email' in df.columns and 'From Date' in df.columns

    if is_ehrms:
        # eHRMS format: S.No, Type, Leave Application No, Employee Name, Email,
        # Designation, From Date, To Date, Apply Status, ...
        df = df.rename(columns={
            'Type': 'leave_type', 'Employee Name': 'emp_name', 'Email': 'email',
            'Designation': 'designation', 'From Date': 'leave_from',
            'To Date': 'leave_to', 'Apply Status': 'leave_status',
        })
    else:
        # Generic format
        df.columns = [c.lower().replace(' ', '_') for c in df.columns]
        required = {'leave_from', 'leave_to', 'leave_type'}
        if not ({'email'} & set(df.columns)) and not ({'emp_code'} & set(df.columns)):
            flash('File must have either "Email" or "emp_code" column.')
            return redirect(url_for('reconciliation.dashboard'))

    batch_id = str(uuid.uuid4())
    count = 0

    # Build email -> emp_code mapping from users table
    from app.models.user import User
    email_to_emp = {}
    for u in User.query.filter(User.email != None, User.email != '').all():
        email_to_emp[u.email.lower().strip()] = u.emp_code
    # Also map by name for fallback
    name_to_emp = {}
    for u in User.query.all():
        name_to_emp[u.name.lower().strip()] = u.emp_code

    for _, row in df.iterrows():
        try:
            # Resolve emp_code from email or direct emp_code
            email = str(row.get('email', '')).strip().lower() if 'email' in df.columns else ''
            emp_code = ''
            if email and email in email_to_emp:
                emp_code = email_to_emp[email]
            elif 'emp_code' in df.columns:
                emp_code = str(row['emp_code']).strip()
            elif 'emp_name' in df.columns:
                name = str(row.get('emp_name', '')).strip().lower()
                emp_code = name_to_emp.get(name, '')

            if not emp_code:
                emp_code = email.split('@')[0] if email else 'unknown'

            leave_from = pd.to_datetime(row['leave_from'], dayfirst=True).date()
            leave_to = pd.to_datetime(row['leave_to'], dayfirst=True).date()
            leave_type = str(row.get('leave_type', '')).strip()
            leave_status = str(row.get('leave_status', 'approved')).strip().lower()
            emp_name = str(row.get('emp_name', '')).strip() if 'emp_name' in df.columns else ''
            days = (leave_to - leave_from).days + 1

            record = EHRMSLeaveRecord(
                upload_batch_id=batch_id, office_id=office_id,
                emp_code=emp_code, emp_name=emp_name,
                leave_from=leave_from, leave_to=leave_to,
                leave_type=leave_type, leave_status=leave_status,
                days=days
            )
            db.session.add(record)
            count += 1
        except Exception:
            continue

    db.session.commit()

    # Run reconciliation
    _run_reconciliation(session_uuid, batch_id)

    AuditLog.log('reconciliation_upload', user_id=current_user.id,
                 details=f'{count} leave records, batch={batch_id[:8]}',
                 ip_address=request.headers.get('X-Forwarded-For', request.remote_addr))

    flash(f'Uploaded {count} leave records. Reconciliation complete.')
    return redirect(url_for('reconciliation.results', batch_id=batch_id,
                            session_uuid=session_uuid))


def _run_reconciliation(session_uuid, batch_id):
    """Match biometric absences against eHRMS leave records."""
    # Load attendance data
    data_path = os.path.join(current_app.config['DATA_FOLDER'], f"{session_uuid}.json")
    if not os.path.exists(data_path):
        return

    with open(data_path) as f:
        data = json.load(f)
    results, start_date, end_date, params = deserialize_results(data)

    # Get all leave records for this batch
    leave_records = EHRMSLeaveRecord.query.filter_by(upload_batch_id=batch_id).all()

    # Build leave lookup: emp_code -> set of dates on leave
    leave_lookup = {}
    for lr in leave_records:
        d = lr.leave_from
        while d <= lr.leave_to:
            leave_lookup.setdefault(lr.emp_code, {})[d] = {
                'type': lr.leave_type,
                'status': lr.leave_status,
            }
            d += timedelta(days=1)

    # Clear old results for this combination
    ReconciliationResult.query.filter_by(
        session_uuid=session_uuid, batch_id=batch_id).delete()
    db.session.commit()

    # Match each employee's absent days
    for r in results:
        emp_code = r['emp_code']
        emp_name = r['emp_name']
        daily = r.get('anomaly_details', [])

        # Check each absent day from biometric
        current = start_date
        while current <= end_date:
            if current.weekday() in (5, 6):  # Skip weekends
                current += timedelta(days=1)
                continue

            # Determine biometric status
            # Check if this date is in the employee's data
            is_absent = False
            is_anomaly = False
            biometric_status = 'present'

            # Check absent days
            if current in [d['date'] for d in r.get('late_arrivals', [])]:
                is_anomaly = True
            if r.get('absent', 0) > 0:
                # We need to check daily_data from the raw results
                pass

            # For simplicity, focus on absent dates (status 'A' in daily data)
            # and anomaly dates
            if current in r.get('all_anomaly_dates', []):
                biometric_status = 'anomaly'
                is_anomaly = True

            # Check eHRMS leave status for this date
            leave_info = leave_lookup.get(emp_code, {}).get(current)
            ehrms_status = 'no_leave'
            leave_type = ''

            if leave_info:
                ehrms_status = f"on_leave_{leave_info['status']}"
                leave_type = leave_info['type']

            # Determine flag
            flag = 'ok'
            remarks = ''

            if biometric_status == 'present' and leave_info and leave_info['status'] == 'approved':
                flag = 'mismatch'
                remarks = f'Present in biometric but on {leave_type} leave in eHRMS'
            elif biometric_status == 'anomaly' and not leave_info:
                # Anomaly but no leave - this is expected (anomaly != absent)
                flag = 'ok'
            elif biometric_status == 'absent' and not leave_info:
                flag = 'absent_no_leave'
                remarks = 'Absent in biometric, no leave record in eHRMS'
            elif biometric_status == 'absent' and leave_info:
                if leave_info['status'] == 'approved':
                    flag = 'matched'
                    remarks = f'Absent, {leave_type} leave approved'
                else:
                    flag = 'leave_unapproved'
                    remarks = f'Absent, {leave_type} leave {leave_info["status"]}'

            # Only save non-OK results to reduce data
            if flag != 'ok':
                db.session.add(ReconciliationResult(
                    session_uuid=session_uuid, batch_id=batch_id,
                    emp_code=emp_code, emp_name=emp_name,
                    record_date=current, biometric_status=biometric_status,
                    ehrms_status=ehrms_status, leave_type=leave_type,
                    flag=flag, remarks=remarks
                ))

            current += timedelta(days=1)

    db.session.commit()


@reconciliation_bp.route('/results/<batch_id>')
@login_required
def results(batch_id):
    if current_user.role not in ('super_admin', 'admin'):
        flash('Access denied.')
        return redirect(url_for('auth.dashboard'))

    session_uuid = request.args.get('session_uuid', '')
    recon_results = ReconciliationResult.query.filter_by(
        batch_id=batch_id
    ).order_by(ReconciliationResult.emp_code, ReconciliationResult.record_date).all()

    # Group by flag type
    by_flag = {}
    for r in recon_results:
        by_flag.setdefault(r.flag, []).append(r)

    # Summary counts
    summary = {flag: len(items) for flag, items in by_flag.items()}

    return render_template('reconciliation/results.html',
                           results=recon_results, by_flag=by_flag,
                           summary=summary, batch_id=batch_id,
                           session_uuid=session_uuid)
