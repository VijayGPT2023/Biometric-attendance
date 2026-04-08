from app.extensions import db
from app.models.base import TimestampMixin


class EmployeeProfile(TimestampMixin, db.Model):
    __tablename__ = 'employee_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey('departments.id'), nullable=True)
    designation_id = db.Column(db.Integer, db.ForeignKey('designation_master.id'), nullable=True)
    date_of_joining = db.Column(db.Date, nullable=True)
    date_of_retirement = db.Column(db.Date, nullable=True)
    date_of_birth = db.Column(db.Date, nullable=True)
    employment_type = db.Column(db.String(30), default='regular')
    phone = db.Column(db.String(15), default='')
    biometric_id = db.Column(db.String(20), nullable=True)  # Maps to XLS emp_code
    gender = db.Column(db.String(10), default='')
    category = db.Column(db.String(20), default='')  # SC/ST/OBC/General
    photo_path = db.Column(db.String(500), nullable=True)

    designation = db.relationship('DesignationMaster')

    __table_args__ = (
        db.Index('ix_empprofile_dept', 'department_id'),
        db.Index('ix_empprofile_biometric', 'biometric_id'),
    )

    def __repr__(self):
        return f'<EmployeeProfile user_id={self.user_id}>'
