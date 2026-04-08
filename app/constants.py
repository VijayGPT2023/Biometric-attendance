"""Application-wide constants and enums."""


class Roles:
    SUPER_ADMIN = 'super_admin'
    ADMIN = 'admin'
    HEAD = 'head'
    EMPLOYEE = 'employee'
    AUDITOR = 'auditor'

    ALL = [SUPER_ADMIN, ADMIN, HEAD, EMPLOYEE, AUDITOR]
    ADMIN_ROLES = [SUPER_ADMIN, ADMIN]
    HEAD_ROLES = [SUPER_ADMIN, ADMIN, HEAD]


class JustificationStatus:
    PENDING = 'pending'
    SUBMITTED = 'submitted'
    ACCEPTED = 'accepted'
    DECLINED = 'declined'
    QUERY = 'query'
    RESUBMITTED = 'resubmitted'


class SessionStatus:
    ACTIVE = 'active'
    FINALIZED = 'finalized'
    ARCHIVED = 'archived'


class ReconciliationFlag:
    MATCHED = 'matched'                     # Absent + leave approved = OK
    ABSENT_WITHOUT_LEAVE = 'absent_no_leave' # Absent + no leave record
    LEAVE_UNAPPROVED = 'leave_unapproved'    # Absent + leave pending
    MISMATCH = 'mismatch'                    # Present + leave approved
    TOUR_EXEMPT = 'tour_exempt'              # On tour = anomaly exempt
    OK = 'ok'                                # No issue


class HolidayType:
    GAZETTED = 'gazetted'
    RESTRICTED = 'restricted'
    OFFICE_SPECIFIC = 'office_specific'
    SPECIAL_WORKING = 'special_working'  # Saturday declared working


class AnomalyType:
    LATE_ARRIVAL = 'late_arrival'
    EARLY_DEPARTURE = 'early_departure'
    SHORT_HOURS = 'short_hours'
    MISSING_PUNCH_IN = 'missing_punch_in'
    MISSING_PUNCH_OUT = 'missing_punch_out'
    ABSENT = 'absent'


class AuditAction:
    LOGIN = 'login'
    LOGOUT = 'logout'
    LOGIN_FAILED = 'login_failed'
    PASSWORD_CHANGE = 'password_change'
    PASSWORD_RESET = 'password_reset'
    USER_CREATE = 'user_create'
    USER_EDIT = 'user_edit'
    USER_DELETE = 'user_delete'
    UPLOAD_XLS = 'upload_xls'
    JUSTIFICATION_SUBMIT = 'justification_submit'
    JUSTIFICATION_REVIEW = 'justification_review'
    FINALIZE = 'finalize'
    OFFICE_CREATE = 'office_create'
    DEPT_CREATE = 'department_create'
    HOLIDAY_CREATE = 'holiday_create'
    CONFIG_CHANGE = 'config_change'
    RECONCILIATION_UPLOAD = 'reconciliation_upload'
    EXPORT_REPORT = 'export_report'
