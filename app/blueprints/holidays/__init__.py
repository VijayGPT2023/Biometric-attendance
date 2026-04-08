from flask import Blueprint

holidays_bp = Blueprint('holidays', __name__, url_prefix='/holidays',
                        template_folder='templates')

from app.blueprints.holidays import routes  # noqa
