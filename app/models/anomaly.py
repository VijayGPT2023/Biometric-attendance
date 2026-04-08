from app.extensions import db
from app.models.base import TimestampMixin


class AnomalyRule(TimestampMixin, db.Model):
    """Configurable anomaly detection rules per office."""
    __tablename__ = 'anomaly_rules'

    id = db.Column(db.Integer, primary_key=True)
    office_id = db.Column(db.Integer, db.ForeignKey('offices.id'), nullable=True)
    rule_name = db.Column(db.String(100), nullable=False)
    threshold_value = db.Column(db.String(50), nullable=False)
    allowed_count = db.Column(db.Integer, default=2)
    leave_deduction_per_anomaly = db.Column(db.Float, default=0.5)
    is_active = db.Column(db.Boolean, default=True)
    description = db.Column(db.Text, default='')

    office = db.relationship('Office', backref='anomaly_rules')

    __table_args__ = (
        db.UniqueConstraint('office_id', 'rule_name', name='uq_anomaly_rule'),
    )

    def __repr__(self):
        return f'<AnomalyRule {self.rule_name}={self.threshold_value}>'
