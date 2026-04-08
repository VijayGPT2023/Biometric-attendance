from flask import Blueprint, jsonify
import traceback

health_bp = Blueprint('health', __name__)


@health_bp.route('/health')
def health():
    return jsonify({'status': 'ok'})


@health_bp.route('/debug-login')
def debug_login():
    """Debug endpoint to diagnose login issues. Remove after fixing."""
    info = {}
    try:
        from app.extensions import db
        import sqlalchemy
        result = db.session.execute(sqlalchemy.text("SELECT COUNT(*) FROM users"))
        info['user_count'] = result.scalar()
        info['db'] = 'connected'
    except Exception as e:
        info['db_error'] = str(e)

    try:
        from flask import render_template_string
        html = render_template_string('{{ csrf_token() }}')
        info['csrf'] = 'ok'
    except Exception as e:
        info['csrf_error'] = str(e)

    try:
        from app.models.user import User
        admin = User.query.filter_by(username='admin').first()
        info['admin_exists'] = bool(admin)
        if admin:
            info['admin_columns'] = [c.name for c in admin.__table__.columns]
    except Exception as e:
        info['user_query_error'] = str(e)

    try:
        from flask import render_template
        render_template('auth/login.html')
        info['template'] = 'ok'
    except Exception as e:
        info['template_error'] = str(e)
        info['template_trace'] = traceback.format_exc()

    return jsonify(info)
