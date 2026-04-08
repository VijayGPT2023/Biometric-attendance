from app.extensions import db
from app.models.base import TimestampMixin

# Association table for head-department mapping
head_departments = db.Table('head_departments',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'),
              primary_key=True),
    db.Column('dept_id', db.Integer, db.ForeignKey('departments.id', ondelete='CASCADE'),
              primary_key=True),
)


class Department(TimestampMixin, db.Model):
    __tablename__ = 'departments'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    name_hi = db.Column(db.String(200), default='')
    code = db.Column(db.String(20), nullable=True)
    office_id = db.Column(db.Integer, db.ForeignKey('offices.id'), nullable=True)
    is_active = db.Column(db.Boolean, default=True)

    employees = db.relationship('EmployeeProfile', backref='department', lazy='dynamic')

    __table_args__ = (
        db.UniqueConstraint('name', 'office_id', name='uq_dept_name_office'),
        db.Index('ix_departments_office', 'office_id'),
    )

    def __repr__(self):
        return f'<Department {self.name}>'
