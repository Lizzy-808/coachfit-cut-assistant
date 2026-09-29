# Deviations from PREREGISTRATION.md

## 1 · The sheet was graded twice (recorded 2026-09-29, before the second grading was read)

**What happened.** The author graded `盲评表_50条.xlsx` once (saved 18:44, about seven minutes after
the sheet was created). That grading was analysed (`results_first_grading.json`, committed). The
author then re-graded a blank copy of the same sheet.

**Why it matters.** The protocol said the sheet is graded once. Choosing between two gradings after
seeing both would let the result pick the grading.

**Rule, fixed before the second grading is opened:**
- The **second grading is the primary result**, because the author re-graded to give each note more
  care than the first, seven-minute pass allowed. This reason does not depend on either result.
- The first grading is reported alongside it, unchanged.
- Agreement between the two gradings (per note and per flag) is reported as test–retest reliability.
- Pass lines, analysis code and cases are unchanged.
