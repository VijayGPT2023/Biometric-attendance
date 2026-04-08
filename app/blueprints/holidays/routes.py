"""Holiday calendar management."""
from datetime import date
from flask import render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models.holiday import Holiday
from app.models.office import Office
from app.models.audit import AuditLog
from app.blueprints.holidays import holidays_bp


@holidays_bp.route('/')
@login_required
def calendar():
    year = request.args.get('year', date.today().year, type=int)
    office_id = request.args.get('office_id', type=int)

    query = Holiday.query.filter_by(year=year, is_active=True)
    if office_id:
        query = query.filter(db.or_(Holiday.office_id == office_id, Holiday.office_id == None))

    holidays = query.order_by(Holiday.holiday_date).all()
    offices = Office.query.filter_by(is_active=True).order_by(Office.name).all()

    return render_template('holidays/calendar.html',
                           holidays=holidays, year=year,
                           offices=offices, selected_office=office_id)


@holidays_bp.route('/add', methods=['POST'])
@login_required
def add():
    if current_user.role not in ('super_admin', 'admin'):
        flash('Access denied.')
        return redirect(url_for('holidays.calendar'))

    holiday_date = request.form.get('holiday_date')
    name = request.form.get('name', '').strip()
    name_hi = request.form.get('name_hi', '').strip()
    holiday_type = request.form.get('holiday_type', 'gazetted')
    office_id = request.form.get('office_id', type=int)

    if holiday_date and name:
        d = date.fromisoformat(holiday_date)
        h = Holiday(
            holiday_date=d, name=name, name_hi=name_hi,
            holiday_type=holiday_type, year=d.year,
            office_id=office_id
        )
        db.session.add(h)
        try:
            db.session.commit()
            AuditLog.log('holiday_create', user_id=current_user.id,
                         resource_type='holiday', resource_id=str(h.id),
                         details=f'{name} on {holiday_date}')
            flash(f'Holiday "{name}" added for {holiday_date}.')
        except Exception:
            db.session.rollback()
            flash('Holiday for this date already exists.')

    return redirect(url_for('holidays.calendar', year=d.year if holiday_date else date.today().year))


@holidays_bp.route('/<int:holiday_id>/delete', methods=['POST'])
@login_required
def delete(holiday_id):
    if current_user.role not in ('super_admin', 'admin'):
        flash('Access denied.')
        return redirect(url_for('holidays.calendar'))

    h = Holiday.query.get_or_404(holiday_id)
    year = h.year
    h.is_active = False
    db.session.commit()
    AuditLog.log('holiday_delete', user_id=current_user.id,
                 resource_type='holiday', resource_id=str(holiday_id))
    flash('Holiday removed.')
    return redirect(url_for('holidays.calendar', year=year))
