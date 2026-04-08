"""Import all models so Alembic can discover them."""
from app.models.office import Office
from app.models.user import User
from app.models.department import Department, head_departments
from app.models.designation import DesignationMaster
from app.models.employee_profile import EmployeeProfile
from app.models.attendance import UploadSession, AttendanceRecord
from app.models.anomaly import AnomalyRule
from app.models.justification import Justification, JustificationCategory
from app.models.holiday import Holiday
from app.models.reconciliation import EHRMSLeaveRecord, ReconciliationResult
from app.models.audit import AuditLog
from app.models.notification import Notification
from app.models.config import SystemConfig, WorkflowConfig

__all__ = [
    'Office', 'User', 'Department', 'head_departments',
    'DesignationMaster', 'EmployeeProfile',
    'UploadSession', 'AttendanceRecord',
    'AnomalyRule', 'Justification', 'JustificationCategory',
    'Holiday', 'EHRMSLeaveRecord', 'ReconciliationResult',
    'AuditLog', 'Notification', 'SystemConfig', 'WorkflowConfig',
]
