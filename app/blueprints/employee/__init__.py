from flask import Blueprint

employee_bp = Blueprint('employee', __name__, url_prefix='/employee',
                        template_folder='templates')

from app.blueprints.employee import routes  # noqa
