"""Application configuration for different environments."""
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
PERSIST_DIR = os.environ.get('RAILWAY_VOLUME_MOUNT_PATH', BASE_DIR)


class BaseConfig:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'npc-biometric-dev-key-change-in-prod')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB

    # File storage
    UPLOAD_FOLDER = os.path.join(PERSIST_DIR, 'uploads')
    DATA_FOLDER = os.path.join(PERSIST_DIR, 'data')

    # Flask-Babel
    BABEL_DEFAULT_LOCALE = 'en'
    BABEL_SUPPORTED_LOCALES = ['en', 'hi']

    # Flask-Mail
    MAIL_SERVER = os.environ.get('MAIL_SERVER', '')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@npcindia.gov.in')

    # Session
    SESSION_TIMEOUT_MINUTES = 30
    PERMANENT_SESSION_LIFETIME = 1800

    # Security
    PASSWORD_EXPIRY_DAYS = 90
    MAX_LOGIN_ATTEMPTS = 5
    LOGIN_LOCKOUT_MINUTES = 15

    # Rate limiting
    RATELIMIT_STORAGE_URI = 'memory://'
    RATELIMIT_DEFAULT = '200/day;50/hour'


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = f'sqlite:///{os.path.join(PERSIST_DIR, "biometric.db")}'
    RATELIMIT_ENABLED = False


class ProductionConfig(BaseConfig):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', '')
    SESSION_COOKIE_SECURE = True
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'


config_map = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig,
}


def get_config(name=None):
    if name is None:
        name = os.environ.get('FLASK_ENV', 'default')
    # Railway sets DATABASE_URL -> auto-detect production
    if os.environ.get('DATABASE_URL'):
        name = 'production'
    return config_map.get(name, DevelopmentConfig)
