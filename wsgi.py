"""WSGI entry point for the application."""
import logging
from app import create_app
from app.extensions import db

app = create_app()
logger = logging.getLogger(__name__)

# Auto-initialize database and seed on first startup
with app.app_context():
    try:
        # v2 migration: if old v1 tables exist with wrong schema, drop and recreate
        import sqlalchemy
        try:
            db.session.execute(sqlalchemy.text("SELECT is_deleted FROM users LIMIT 1"))
            logger.info("v2 schema detected.")
        except Exception:
            db.session.rollback()
            logger.info("v1 or fresh DB. Dropping for clean v2...")
            db.drop_all()

        db.create_all()
        logger.info("Database tables ready.")

        from app.models.user import User
        if not User.query.filter_by(username='admin').first():
            logger.info("Seeding...")
            from app.seeds import seed_all
            seed_all()
            logger.info("Seed complete.")
        else:
            logger.info("Already seeded.")
    except Exception as e:
        logger.error(f"DB init error: {e}", exc_info=True)


if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'true').lower() == 'true'
    app.run(debug=debug, host='0.0.0.0', port=port)
