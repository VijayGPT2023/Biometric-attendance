"""Authentication routes: login, logout, password change, forgot password."""
import uuid
from datetime import datetime
from flask import render_template, request, redirect, url_for, flash, session, current_app
from flask_login import login_user, logout_user, login_required, current_user
from app.extensions import db
from app.models.user import User
from app.models.audit import AuditLog
from app.blueprints.auth import auth_bp


def _get_client_ip():
    return request.headers.get('X-Forwarded-For', request.remote_addr)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth.dashboard'))

    if request.method == 'POST':
        login_id = request.form.get('username', '').strip().lower()
        password = request.form.get('password', '')
        ip = _get_client_ip()

        try:
            user = User.query.filter(
                db.or_(
                    db.func.lower(User.username) == login_id,
                    User.emp_code == login_id
                ),
                User.is_active == True,
            ).first()
        except Exception as e:
            current_app.logger.error(f"Login query error: {e}")
            user = None

        if user and user.is_locked():
            flash('Account is locked due to too many failed attempts. Try again later.')
            return render_template('auth/login.html')

        if user and user.check_password(password):
            # Concurrent session handling
            if user.active_session_id:
                if user.last_activity:
                    elapsed = (datetime.utcnow() - user.last_activity).total_seconds()
                    timeout = current_app.config.get('SESSION_TIMEOUT_MINUTES', 30) * 60
                    if elapsed < timeout:
                        flash('Note: Your previous session has been terminated.')

            # Login success
            new_sid = str(uuid.uuid4())
            user.active_session_id = new_sid
            user.last_activity = datetime.utcnow()
            user.last_login_ip = ip
            user.failed_login_count = 0
            user.locked_until = None
            db.session.commit()

            login_user(user)
            session['session_token'] = new_sid
            session['last_activity'] = datetime.utcnow().isoformat()

            AuditLog.log('login', user_id=user.id, ip_address=ip)
            current_app.logger.info(f"Login: {user.username} ({user.role}) from {ip}")

            if user.must_change_password:
                flash('Please change your default password to continue.')
                return redirect(url_for('auth.change_password'))

            return redirect(url_for('auth.dashboard'))

        # Login failed
        if user:
            user.failed_login_count = (user.failed_login_count or 0) + 1
            max_attempts = current_app.config.get('MAX_LOGIN_ATTEMPTS', 5)
            if user.failed_login_count >= max_attempts:
                from datetime import timedelta
                lockout_mins = current_app.config.get('LOGIN_LOCKOUT_MINUTES', 15)
                user.locked_until = datetime.utcnow() + timedelta(minutes=lockout_mins)
                flash(f'Account locked for {lockout_mins} minutes due to too many failed attempts.')
            db.session.commit()

        AuditLog.log('login_failed', details=f'username={login_id}', ip_address=ip)
        current_app.logger.info(f"Failed login: '{login_id}' from {ip}")
        flash('Invalid Username or Password')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    if current_user.is_authenticated:
        AuditLog.log('logout', user_id=current_user.id, ip_address=_get_client_ip())
        current_user.active_session_id = ''
        current_user.last_activity = None
        db.session.commit()
    logout_user()
    session.clear()
    flash('You have been logged out.')
    return redirect(url_for('auth.login'))


@auth_bp.route('/')
@login_required
def dashboard():
    if current_user.must_change_password:
        return redirect(url_for('auth.change_password'))
    role = current_user.role
    if role in ('super_admin', 'admin'):
        return redirect(url_for('admin.dashboard'))
    elif role == 'head':
        return redirect(url_for('head.dashboard'))
    else:
        return redirect(url_for('employee.dashboard'))


@auth_bp.route('/placeholder/<page>')
@login_required
def placeholder(page):
    return render_template('auth/placeholder.html', page=page)


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        old_pw = request.form.get('old_password', '')
        new_pw = request.form.get('new_password', '')
        confirm = request.form.get('confirm_password', '')

        if new_pw != confirm:
            flash('New passwords do not match.')
            return redirect(url_for('auth.change_password'))

        # Password strength
        errors = _validate_password(new_pw)
        if errors:
            flash(errors)
            return redirect(url_for('auth.change_password'))

        if not current_user.check_password(old_pw):
            flash('Current password is incorrect.')
            return redirect(url_for('auth.change_password'))

        current_user.set_password(new_pw)
        current_user.must_change_password = False
        db.session.commit()

        AuditLog.log('password_change', user_id=current_user.id, ip_address=_get_client_ip())
        flash('Password changed successfully.')
        return redirect(url_for('auth.dashboard'))

    forced = current_user.must_change_password
    return render_template('auth/change_password.html', forced=forced)


@auth_bp.route('/forgot-password')
def forgot_password():
    return render_template('auth/forgot_password.html')


def _validate_password(pw):
    if len(pw) < 8:
        return 'Password must be at least 8 characters long.'
    if not any(c.isalpha() for c in pw):
        return 'Password must contain at least one letter.'
    if not any(c.isdigit() for c in pw):
        return 'Password must contain at least one number.'
    return None
