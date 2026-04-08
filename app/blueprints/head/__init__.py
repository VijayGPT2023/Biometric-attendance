from flask import Blueprint

head_bp = Blueprint('head', __name__, url_prefix='/head',
                    template_folder='templates')

from app.blueprints.head import routes  # noqa
