from app.extensions import db
from app.models.base import TimestampMixin


class JustificationCategory(TimestampMixin, db.Model):
    __tablename__ = 'justification_categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    name_hi = db.Column(db.String(200), default='')
    requires_document = db.Column(db.Boolean, default=False)
    auto_exclude = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<JustificationCategory {self.name}>'


class Justification(TimestampMixin, db.Model):
    __tablename__ = 'justifications'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('upload_sessions.id'), nullable=False)
    session_uuid = db.Column(db.String(36), nullable=False)
    emp_code = db.Column(db.String(20), nullable=False)
    anomaly_date = db.Column(db.Date, nullable=False)
    anomaly_types = db.Column(db.String(200), default='')
    category_id = db.Column(db.Integer, db.ForeignKey('justification_categories.id'),
                            nullable=True)
    justification = db.Column(db.Text, default='')
    document_path = db.Column(db.String(500), nullable=True)
    status = db.Column(db.String(20), default='pending')
    head_remark = db.Column(db.Text, default='')
    head_reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    head_reviewed_at = db.Column(db.DateTime, nullable=True)
    admin_remark = db.Column(db.Text, default='')
    admin_reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    admin_reviewed_at = db.Column(db.DateTime, nullable=True)
    query_count = db.Column(db.Integer, default=0)  # Max 2 queries allowed
    employee_reply = db.Column(db.Text, default='')  # Reply to head's query
    finalized = db.Column(db.Boolean, default=False)
    final_decision = db.Column(db.String(20), default='')

    category = db.relationship('JustificationCategory')

    __table_args__ = (
        db.UniqueConstraint('session_uuid', 'emp_code', 'anomaly_date',
                            name='uq_justification'),
        db.Index('ix_just_session_emp', 'session_uuid', 'emp_code'),
        db.Index('ix_just_status', 'status'),
    )
