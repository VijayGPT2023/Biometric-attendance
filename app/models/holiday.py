from app.extensions import db
from app.models.base import TimestampMixin


class Holiday(TimestampMixin, db.Model):
    __tablename__ = 'holidays'

    id = db.Column(db.Integer, primary_key=True)
    holiday_date = db.Column(db.Date, nullable=False)
    name = db.Column(db.String(200), nullable=False)
    name_hi = db.Column(db.String(200), default='')
    holiday_type = db.Column(db.String(30), nullable=False)  # gazetted, restricted, office_specific
    office_id = db.Column(db.Integer, db.ForeignKey('offices.id'), nullable=True)
    year = db.Column(db.Integer, nullable=False)
    is_active = db.Column(db.Boolean, default=True)

    office = db.relationship('Office', backref='holidays')

    __table_args__ = (
        db.UniqueConstraint('holiday_date', 'office_id', name='uq_holiday_date_office'),
        db.Index('ix_holidays_year', 'year'),
        db.Index('ix_holidays_date', 'holiday_date'),
    )

    def __repr__(self):
        return f'<Holiday {self.holiday_date} {self.name}>'
