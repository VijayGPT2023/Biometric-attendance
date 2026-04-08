from datetime import datetime
from app.extensions import db


class AuditLog(db.Model):
    """Immutable audit trail - append only."""
    __tablename__ = 'audit_log'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    resource_type = db.Column(db.String(50), default='')
    resource_id = db.Column(db.String(50), default='')
    details = db.Column(db.Text, default='')
    ip_address = db.Column(db.String(45), default='')
    user_agent = db.Column(db.String(500), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref='audit_logs')

    __table_args__ = (
        db.Index('ix_audit_user', 'user_id'),
        db.Index('ix_audit_action', 'action'),
        db.Index('ix_audit_created', 'created_at'),
        db.Index('ix_audit_resource', 'resource_type', 'resource_id'),
    )

    @classmethod
    def log(cls, action, user_id=None, resource_type='', resource_id='',
            details='', ip_address='', user_agent=''):
        entry = cls(
            user_id=user_id, action=action,
            resource_type=resource_type, resource_id=str(resource_id),
            details=details, ip_address=ip_address, user_agent=user_agent)
        db.session.add(entry)
        db.session.commit()
        return entry
