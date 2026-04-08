from flask import Blueprint

settings_bp = Blueprint('settings', __name__, url_prefix='/settings',
                        template_folder='templates')

from app.blueprints.settings import routes  # noqa
