from flask import Blueprint

reconciliation_bp = Blueprint('reconciliation', __name__, url_prefix='/reconciliation',
                              template_folder='templates')

from app.blueprints.reconciliation import routes  # noqa
