from app.extensions import db
from app.models.base import TimestampMixin


class Office(TimestampMixin, db.Model):
    __tablename__ = 'offices'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    name_hi = db.Column(db.String(200), default='')
    code = db.Column(db.String(20), unique=True, nullable=False)
    location = db.Column(db.String(200), default='')
    state = db.Column(db.String(100), default='')
    address = db.Column(db.Text, default='')
    is_active = db.Column(db.Boolean, default=True)

    # Default office timing (can be overridden by anomaly_rules)
    work_start_time = db.Column(db.String(5), default='09:00')
    work_end_time = db.Column(db.String(5), default='17:30')
    grace_minutes = db.Column(db.Integer, default=15)

    users = db.relationship('User', backref='office', lazy='dynamic')
    departments = db.relationship('Department', backref='office', lazy='dynamic')

    def __repr__(self):
        return f'<Office {self.code}: {self.name}>'
