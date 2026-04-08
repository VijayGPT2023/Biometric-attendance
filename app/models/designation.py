from app.extensions import db
from app.models.base import TimestampMixin


class DesignationMaster(TimestampMixin, db.Model):
    __tablename__ = 'designation_master'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    name_hi = db.Column(db.String(200), default='')
    level = db.Column(db.Integer, nullable=True)  # Pay level
    category = db.Column(db.String(50), default='')  # Group A/B/C/D
    is_active = db.Column(db.Boolean, default=True)

    def __repr__(self):
        return f'<Designation {self.name}>'
