---
name: Query-reply cycle limited to max 2 rounds
description: GH can query employee max 2 times. Employee must have reply option. After 2 queries, GH must accept or decline.
type: feedback
---

Query workflow (Top Management feedback 2026-04-10):
- GH raises query → Employee sees query WITH reply option (currently no reply option - BUG)
- Employee replies → GH reviews again
- GH can query again (2nd time) → Employee replies again
- After 2 query rounds, GH MUST accept or decline (no more queries allowed)
- Track query_count per justification

**Why:** Prevents endless back-and-forth. Forces decision within reasonable rounds.

**How to apply:** Add query_count to justifications table. Employee report must show reply textbox when status='query'. GH review hides query option when query_count >= 2.
