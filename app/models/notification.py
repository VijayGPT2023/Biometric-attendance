from app.extensions import db
from app.models.base import TimestampMixin


class Notification(TimestampMixin, db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(30), default='info')
    link = db.Column(db.String(500), nullable=True)
    is_read = db.Column(db.Boolean, default=False)
    is_email_sent = db.Column(db.Boolean, default=False)

    user = db.relationship('User', backref='notifications')

    __table_args__ = (
        db.Index('ix_notif_user_read', 'user_id', 'is_read'),
    )
