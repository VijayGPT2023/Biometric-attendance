from app.extensions import db
from app.models.base import TimestampMixin


class UploadSession(TimestampMixin, db.Model):
    __tablename__ = 'upload_sessions'

    id = db.Column(db.Integer, primary_key=True)
    session_uuid = db.Column(db.String(36), unique=True, nullable=False)
    office_id = db.Column(db.Integer, db.ForeignKey('offices.id'), nullable=True)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)
    params_json = db.Column(db.Text, nullable=False)
    data_file_path = db.Column(db.String(500), default='')
    status = db.Column(db.String(20), default='active')
    employee_count = db.Column(db.Integer, default=0)
    anomaly_count = db.Column(db.Integer, default=0)
    original_filenames = db.Column(db.Text, default='')

    office = db.relationship('Office', backref='upload_sessions')
    uploader = db.relationship('User', backref='uploaded_sessions')
    records = db.relationship('AttendanceRecord', backref='session',
                              lazy='dynamic', cascade='all, delete-orphan')
    justifications = db.relationship('Justification', backref='session',
                                     lazy='dynamic', cascade='all, delete-orphan')

    __table_args__ = (
        db.Index('ix_upload_sessions_office', 'office_id'),
        db.Index('ix_upload_sessions_dates', 'start_date', 'end_date'),
        db.Index('ix_upload_sessions_status', 'status'),
    )

    def __repr__(self):
        return f'<UploadSession {self.session_uuid[:8]} {self.start_date}-{self.end_date}>'


class AttendanceRecord(db.Model):
    """Individual daily attendance record per employee."""
    __tablename__ = 'attendance_records'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('upload_sessions.id'), nullable=False)
    emp_code = db.Column(db.String(20), nullable=False)
    emp_name = db.Column(db.String(200), default='')
    department = db.Column(db.String(200), default='')
    designation = db.Column(db.String(200), default='')
    attendance_date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(10), default='')
    raw_status = db.Column(db.String(20), default='')
    arrival_time = db.Column(db.String(10), nullable=True)
    departure_time = db.Column(db.String(10), nullable=True)
    working_hours = db.Column(db.String(10), default='')
    working_minutes = db.Column(db.Integer, default=0)
    is_anomaly = db.Column(db.Boolean, default=False)
    anomaly_types = db.Column(db.String(200), default='')
    is_weekend = db.Column(db.Boolean, default=False)
    is_holiday = db.Column(db.Boolean, default=False)

    __table_args__ = (
        db.UniqueConstraint('session_id', 'emp_code', 'attendance_date',
                            name='uq_attendance_record'),
        db.Index('ix_att_emp_date', 'emp_code', 'attendance_date'),
        db.Index('ix_att_session', 'session_id'),
        db.Index('ix_att_anomaly', 'is_anomaly'),
    )
