from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from app.models.base import TimestampMixin, SoftDeleteMixin


class User(UserMixin, TimestampMixin, SoftDeleteMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    emp_code = db.Column(db.String(20), nullable=False)
    username = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    name_hi = db.Column(db.String(200), default='')
    email = db.Column(db.String(254), nullable=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='employee')
    is_active = db.Column(db.Boolean, default=True)
    must_change_password = db.Column(db.Boolean, default=True)
    password_changed_at = db.Column(db.DateTime, nullable=True)
    active_session_id = db.Column(db.String(64), default='')
    last_activity = db.Column(db.DateTime, nullable=True)
    last_login_ip = db.Column(db.String(45), default='')
    failed_login_count = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)
    office_id = db.Column(db.Integer, db.ForeignKey('offices.id'), nullable=True)
    preferred_language = db.Column(db.String(5), default='en')

    # Relationships
    profile = db.relationship('EmployeeProfile', backref='user', uselist=False,
                              cascade='all, delete-orphan')
    head_departments = db.relationship('Department', secondary='head_departments',
                                       backref='heads', lazy='dynamic')

    __table_args__ = (
        db.UniqueConstraint('emp_code', 'office_id', name='uq_user_emp_office'),
        db.Index('ix_users_emp_code', 'emp_code'),
        db.Index('ix_users_role', 'role'),
        db.Index('ix_users_office', 'office_id'),
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        self.password_changed_at = datetime.utcnow()

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_password_expired(self, expiry_days=90):
        if not self.password_changed_at:
            return True
        delta = (datetime.utcnow() - self.password_changed_at).days
        return delta > expiry_days

    def is_locked(self):
        if self.locked_until and self.locked_until > datetime.utcnow():
            return True
        return False

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'
