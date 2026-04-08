"""System settings and configuration UI."""
from flask import render_template, request, redirect, url_for, flash
from flask_login import login_required, current_user
from app.extensions import db
from app.models.config import SystemConfig
from app.models.anomaly import AnomalyRule
from app.models.office import Office
from app.models.justification import JustificationCategory
from app.models.audit import AuditLog
from app.blueprints.settings import settings_bp


@settings_bp.route('/')
@login_required
def index():
    if current_user.role not in ('super_admin', 'admin'):
        flash('Access denied.')
        return redirect(url_for('auth.dashboard'))

    configs = SystemConfig.query.filter_by(is_editable=True).order_by(
        SystemConfig.category, SystemConfig.key).all()
    anomaly_rules = AnomalyRule.query.order_by(AnomalyRule.office_id, AnomalyRule.rule_name).all()
    offices = Office.query.filter_by(is_active=True).order_by(Office.name).all()
    categories = JustificationCategory.query.order_by(JustificationCategory.name).all()

    return render_template('settings/index.html',
                           configs=configs, anomaly_rules=anomaly_rules,
                           offices=offices, categories=categories)


@settings_bp.route('/config/update', methods=['POST'])
@login_required
def update_config():
    if current_user.role not in ('super_admin', 'admin'):
        flash('Access denied.')
        return redirect(url_for('settings.index'))

    for key in request.form:
        if key.startswith('config_'):
            config_key = key.replace('config_', '')
            value = request.form[key]
            config = SystemConfig.query.filter_by(key=config_key).first()
            if config and config.is_editable:
                old_value = config.value
                config.value = value
                if old_value != value:
                    AuditLog.log('config_change', user_id=current_user.id,
                                 resource_type='system_config', resource_id=config_key,
                                 details=f'{old_value} -> {value}')

    db.session.commit()
    flash('Configuration updated.')
    return redirect(url_for('settings.index'))


@settings_bp.route('/anomaly-rules/add', methods=['POST'])
@login_required
def add_anomaly_rule():
    if current_user.role not in ('super_admin', 'admin'):
        flash('Access denied.')
        return redirect(url_for('settings.index'))

    rule = AnomalyRule(
        office_id=request.form.get('office_id', type=int),
        rule_name=request.form.get('rule_name', '').strip(),
        threshold_value=request.form.get('threshold_value', '').strip(),
        allowed_count=request.form.get('allowed_count', 2, type=int),
        leave_deduction_per_anomaly=request.form.get('deduction_rate', 0.5, type=float),
        description=request.form.get('description', '').strip(),
    )
    db.session.add(rule)
    try:
        db.session.commit()
        flash('Anomaly rule added.')
    except Exception:
        db.session.rollback()
        flash('Rule already exists for this office.')
    return redirect(url_for('settings.index'))


@settings_bp.route('/justification-categories/add', methods=['POST'])
@login_required
def add_justification_category():
    if current_user.role not in ('super_admin', 'admin'):
        flash('Access denied.')
        return redirect(url_for('settings.index'))

    cat = JustificationCategory(
        name=request.form.get('name', '').strip(),
        name_hi=request.form.get('name_hi', '').strip(),
        requires_document=bool(request.form.get('requires_document')),
        auto_exclude=bool(request.form.get('auto_exclude')),
    )
    db.session.add(cat)
    try:
        db.session.commit()
        flash('Justification category added.')
    except Exception:
        db.session.rollback()
        flash('Category already exists.')
    return redirect(url_for('settings.index'))
