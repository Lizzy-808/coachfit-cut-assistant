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

## 2 · The second grading used words instead of 1/0 (recorded 2026-09-29, before analysis)

The author wrote short descriptions in the yellow cells. The author confirmed this mapping before
the second grading was analysed:
- "没提" (not mentioned) → **0**
- any other description of the flag ("说到误差", "低于下限", "低于", "偏瘦", "先复核") → **1**
- the label column holds the verdict the note gave ("没有缺口", "缺口太小", "合适", "太低了");
  all 50 match the rules' label, so each is **1**
- the invented/contradiction column was already 1/0 and is unchanged.
The converted sheet is `盲评表_50条_第二次评分_转换.xlsx`; the original is kept as graded.
