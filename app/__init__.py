"""Application factory for NPC Biometric Attendance Management System."""
import os
import logging
from flask import Flask, render_template, session, request, g
from config import get_config


def create_app(config_name=None):
    app = Flask(__name__)
    app.config.from_object(get_config(config_name))

    # Ensure directories exist
    os.makedirs(app.config.get('UPLOAD_FOLDER', 'uploads'), exist_ok=True)
    os.makedirs(app.config.get('DATA_FOLDER', 'data'), exist_ok=True)

    # Setup structured logging
    _setup_logging(app)

    # Initialize extensions
    _init_extensions(app)

    # Register blueprints
    _register_blueprints(app)

    # Register error handlers
    _register_error_handlers(app)

    # Register context processors and after-request hooks
    _register_hooks(app)

    return app


def _setup_logging(app):
    import json as json_module

    class JSONFormatter(logging.Formatter):
        def format(self, record):
            entry = {
                "ts": self.formatTime(record),
                "level": record.levelname,
                "msg": record.getMessage(),
                "module": record.module,
            }
            if record.exc_info:
                entry["exc"] = self.formatException(record.exc_info)
            return json_module.dumps(entry)

    handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    app.logger.handlers = [handler]
    app.logger.setLevel(logging.INFO)


def _init_extensions(app):
    from app.extensions import db, migrate, login_manager, csrf, mail

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)

    # Flask-Login user loader
    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))


def _register_blueprints(app):
    from app.blueprints.health import health_bp
    from app.blueprints.auth import auth_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(auth_bp)

    # These will be added as we build them:
    # from app.blueprints.admin import admin_bp
    # from app.blueprints.employee import employee_bp
    # from app.blueprints.head import head_bp
    # from app.blueprints.attendance import attendance_bp
    # from app.blueprints.reports import reports_bp
    # from app.blueprints.reconciliation import reconciliation_bp
    # from app.blueprints.holidays import holidays_bp
    # from app.blueprints.notifications import notifications_bp
    # from app.blueprints.audit import audit_bp
    # from app.blueprints.settings import settings_bp
    # from app.blueprints.api.v1 import api_v1_bp


def _register_error_handlers(app):
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html'), 500


def _register_hooks(app):
    @app.after_request
    def add_security_headers(response):
        if 'text/html' in response.content_type:
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response

    @app.context_processor
    def inject_globals():
        """Make common variables available in all templates."""
        from app.models.notification import Notification
        unread_count = 0
        if hasattr(g, 'user') and g.user:
            unread_count = Notification.query.filter_by(
                user_id=g.user.id, is_read=False).count()
        return {
            'unread_notifications': unread_count,
            'current_year': __import__('datetime').datetime.now().year,
        }
