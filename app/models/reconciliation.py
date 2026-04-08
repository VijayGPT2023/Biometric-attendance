from app.extensions import db
from app.models.base import TimestampMixin


class EHRMSLeaveRecord(TimestampMixin, db.Model):
    """Leave records imported from eHRMS for reconciliation."""
    __tablename__ = 'ehrms_leave_records'

    id = db.Column(db.Integer, primary_key=True)
    upload_batch_id = db.Column(db.String(36), nullable=False)  # Group by upload
    office_id = db.Column(db.Integer, db.ForeignKey('offices.id'), nullable=True)
    emp_code = db.Column(db.String(20), nullable=False)
    emp_name = db.Column(db.String(200), default='')
    leave_from = db.Column(db.Date, nullable=False)
    leave_to = db.Column(db.Date, nullable=False)
    leave_type = db.Column(db.String(20), default='')  # CL, EL, HPL, etc.
    leave_status = db.Column(db.String(20), default='approved')  # approved, pending, rejected
    days = db.Column(db.Float, default=0)
    remarks = db.Column(db.Text, default='')

    office = db.relationship('Office')

    __table_args__ = (
        db.Index('ix_ehrms_emp_dates', 'emp_code', 'leave_from', 'leave_to'),
        db.Index('ix_ehrms_batch', 'upload_batch_id'),
    )


class ReconciliationResult(TimestampMixin, db.Model):
    """Result of matching biometric absence vs eHRMS leave records."""
    __tablename__ = 'reconciliation_results'

    id = db.Column(db.Integer, primary_key=True)
    session_uuid = db.Column(db.String(36), nullable=False)  # Attendance session
    batch_id = db.Column(db.String(36), nullable=False)  # eHRMS upload batch
    emp_code = db.Column(db.String(20), nullable=False)
    emp_name = db.Column(db.String(200), default='')
    record_date = db.Column(db.Date, nullable=False)
    biometric_status = db.Column(db.String(20), default='')  # present, absent, anomaly
    ehrms_status = db.Column(db.String(30), default='')  # on_leave, no_leave, on_tour
    leave_type = db.Column(db.String(20), default='')
    flag = db.Column(db.String(30), nullable=False)  # matched, absent_no_leave, mismatch, etc.
    remarks = db.Column(db.Text, default='')
    reviewed = db.Column(db.Boolean, default=False)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    review_remark = db.Column(db.Text, default='')

    __table_args__ = (
        db.UniqueConstraint('session_uuid', 'batch_id', 'emp_code', 'record_date',
                            name='uq_reconciliation'),
        db.Index('ix_recon_flag', 'flag'),
        db.Index('ix_recon_emp', 'emp_code'),
    )
