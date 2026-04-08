"""WSGI entry point for the application."""
import logging
from app import create_app
from app.extensions import db

app = create_app()
logger = logging.getLogger(__name__)

# Auto-initialize database and seed on first startup
with app.app_context():
    try:
        db.create_all()
        logger.info("Database tables ensured.")

        # Seed if admin user doesn't exist (first startup)
        from app.models.user import User
        if not User.query.filter_by(username='admin').first():
            logger.info("First startup detected - seeding data...")
            from manage import (_seed_offices, _seed_admin, _seed_departments,
                                _seed_head_accounts, _seed_employees, _seed_holidays_2026)
            _seed_offices()
            _seed_admin()
            _seed_departments()
            _seed_head_accounts()
            _seed_employees()
            _seed_holidays_2026()
            logger.info("Seed complete: 160 users, 12 departments, 18 holidays")
        else:
            logger.info("Database already seeded.")
    except Exception as e:
        logger.error(f"Database init error: {e}", exc_info=True)


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'true').lower() == 'true'
    app.run(debug=debug, host='0.0.0.0', port=port)
