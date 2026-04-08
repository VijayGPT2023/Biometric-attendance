from app.extensions import db
from app.models.base import TimestampMixin


class SystemConfig(TimestampMixin, db.Model):
    """Key-value configuration store. All business rules here, not in code."""
    __tablename__ = 'system_config'

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=False)
    value_type = db.Column(db.String(20), default='string')  # string, int, float, bool, json
    category = db.Column(db.String(50), default='general')
    description = db.Column(db.Text, default='')
    is_editable = db.Column(db.Boolean, default=True)

    __table_args__ = (
        db.Index('ix_sysconfig_category', 'category'),
    )

    @classmethod
    def get(cls, key, default=None):
        row = cls.query.filter_by(key=key).first()
        if not row:
            return default
        if row.value_type == 'int':
            return int(row.value)
        elif row.value_type == 'float':
            return float(row.value)
        elif row.value_type == 'bool':
            return row.value.lower() in ('true', '1', 'yes')
        elif row.value_type == 'json':
            import json
            return json.loads(row.value)
        return row.value

    @classmethod
    def set(cls, key, value, value_type='string', category='general', description=''):
        row = cls.query.filter_by(key=key).first()
        if row:
            row.value = str(value)
        else:
            row = cls(key=key, value=str(value), value_type=value_type,
                      category=category, description=description)
            db.session.add(row)
        db.session.commit()


class WorkflowConfig(TimestampMixin, db.Model):
    __tablename__ = 'workflow_config'

    id = db.Column(db.Integer, primary_key=True)
    workflow_name = db.Column(db.String(100), nullable=False)
    step_order = db.Column(db.Integer, nullable=False)
    step_name = db.Column(db.String(100), nullable=False)
    required_role = db.Column(db.String(20), nullable=False)
    auto_escalate_hours = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)

    __table_args__ = (
        db.UniqueConstraint('workflow_name', 'step_order', name='uq_workflow_step'),
    )
