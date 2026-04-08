from flask import Blueprint

audit_bp = Blueprint('audit', __name__, url_prefix='/audit',
                     template_folder='templates')

from app.blueprints.audit import routes  # noqa
