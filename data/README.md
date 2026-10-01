# Data

One file: **`nhanes_fatloss_800.xlsx`** — 800 US adults aged 20–35 from NHANES, prepared by the
author for PE6201 A1 Part 1 and reused here unchanged.

| | |
|---|---|
| Source | US National Health and Nutrition Examination Survey (CDC), https://wwwn.cdc.gov/nchs/nhanes/ |
| Licence | US federal public-domain data — redistribution allowed, so the file ships with the repo |
| Rows | 800 (one sheet, `nhanes_fatloss_sample_800_2021_`) |
| Personal data | None: `participant_id` is a 1–800 renumbering, not the NHANES respondent ID |
| Used by | `eval/run_eval.py`, `eval/heldout_v3.py`, `eval/confirmatory.py`, `eval/cost_to_serve.py` |

## Columns

| Column | Meaning | Used by the code? |
|---|---|---|
| `participant_id` | 1–800, assigned in A1 | yes — case IDs `N<id>` in every eval file |
| `age_years`, `sex`, `height_cm`, `weight_kg` | measured body data | yes — input |
| `daily_kcal` | reported daily energy intake | yes — input |
| `activity_level` | `sedentary` / `low` / `moderate` / `high` | yes — mapped to the app's `sedentary` / `light` / `moderate` / `active` |
| `activity_factor` | 1.2 / 1.375 / 1.55 / 1.725 | no — the code applies its own factors (identical values) |
| `height_m`, `bmi`, `BMR`, `TDEE`, `deficit`, `deficit_min`, `deficit_max` | values computed **in Excel** in A1 | no — reference only |
| `label` | reference label computed **in Excel** in A1 (Chinese) | yes — ground truth for evaluation part A |

`label` values: 没有热量缺口 = `no_deficit` (238 rows) · 缺口过小 = `too_small` (144) ·
缺口合适 = `appropriate` (187) · 缺口过大 = `too_large` (231).

The Excel-computed columns are never given to the code as input — the code recomputes everything
from the raw measurements. That is what makes part A ("rules vs Excel: 787/787") an independent
check of the implementation rather than a copy.

## Known issues (all reported, none hidden)

| Issue | Effect | How it is handled |
|---|---|---|
| 13 rows have impossible intake (e.g. 45 kcal/day, ~0 kcal/day) | would produce nonsense labels | the rules refuse them (`status = abstain`); reported in part A |
| One-day recalls under-report intake | 18.5% of rows fall below the 1,200/1,500 kcal safety floor | those cases are routed to the coach; discussed as a data-readiness failure in the report |
| **No protein column** — lost when the extract was prepared in A1 | a protein rule could not be validated on real data | protein was removed from scope on 2026-09-28 |
| Survey cycle and intake variable were not recorded in A1 | provenance is incomplete | stated as a limitation in the report and problem statement |
| Activity level is respondent-level, not measured | TDEE carries the error of a self-reported activity factor | inherent to the method; not corrected |

## Other inputs

`eval/handwritten_cases.csv` — 14 edge cases written by hand (safety, borderline, invalid input,
typical). The expected outcome of each case was fixed in the file **before** any run; two
expectations were corrected after a hand-check of the formula, and the `why` column records it.
