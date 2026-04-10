---
name: Leave deduction formula change - monthly reset with ROUNDDOWN(anomaly/3)
description: Leave deduction is monthly (not cumulative), formula is ROUNDDOWN(anomaly_days/3, 0), resets each month. NOT 0.5 per extra day.
type: feedback
---

Leave deduction formula CHANGED by Top Management on 2026-04-10:

**Old rule (WRONG):** 2 free anomalies per month, then 0.5 EL per extra day
**New rule (CORRECT):** Leave deducted = ROUNDDOWN(anomaly_days / 3, 0) per month

Examples:
- 1-2 anomaly days = 0 leave deducted
- 3-5 anomaly days = 1 leave deducted  
- 6-8 anomaly days = 2 leaves deducted
- 9-11 anomaly days = 3 leaves deducted

**Critical:** Monthly data ONLY. Month-1 having 1 anomaly and Month-2 having 2 anomalies do NOT add up. Each month is calculated independently.

**Why:** This is the actual NPC/government rule for attendance-based leave deduction.

**How to apply:** Update analyze_employee() function, all templates showing leave deduction, PPT slides, and landing page formula.
