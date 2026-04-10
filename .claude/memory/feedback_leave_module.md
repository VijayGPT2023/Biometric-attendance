---
name: No leave application module - use eHRMS reconciliation instead
description: User does NOT want leave apply/approve on this portal. Leave is managed on eHRMS. This portal should only reconcile absence vs eHRMS leave data.
type: feedback
---

Do NOT build leave application/approval workflow in this portal. Leave management (apply, approve, reject) is done on eHRMS (Manav Sampada).

**Why:** NPC already uses eHRMS for leave management. Duplicating it would create data conflicts.

**How to apply:** Instead, build a Leave Reconciliation module:
1. Admin downloads leave data from eHRMS (CSV/Excel export)
2. Upload to this portal
3. System matches: biometric absent dates vs eHRMS approved leave dates
4. Flags discrepancies:
   - Absent in biometric BUT no leave on eHRMS = "Absent Without Leave" (needs investigation)
   - On leave in eHRMS BUT present in biometric = "Leave mismatch" (may be cancelled leave)
   - On tour (not on leave) BUT absent in biometric = valid (mark as tour)
5. This reconciliation report goes to HoD/Admin for action
