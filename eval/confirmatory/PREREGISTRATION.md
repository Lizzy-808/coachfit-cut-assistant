# Confirmatory test of the flag-coverage guard — pre-registration

Author: LIU ZEYUAN · Written 2026-09-29, **before any note for this test was generated**.
This file is committed to git before `eval/confirmatory.py generate` is run; the commit timestamp
is the proof. Nothing below may change after generation. Any deviation is recorded in
`DEVIATIONS.md` with its reason, and the original plan stays here.

## Why a new test

Earlier hand-graded runs were exploratory and cannot support a v2-vs-v3 comparison:
v2 and v3 were graded on different cases, under different scopes (protein in / out), with the
grader knowing which version was the improved one. Their results are kept as development history.

## Question

The v3 guard appends any flag the model's note leaves out. Its only way to fail silently is the
**detector**: if a flag is missing but the detector thinks it is present, nothing is appended.
So the test asks:

1. After the guard, do coach notes state every flag the rules raised and invent none?
2. When the model leaves a flag out, how often does the detector catch it?
3. Does appending text ever introduce an invented flag or a contradiction?

## Frozen system

Code as of the commit that adds this file: `coachfit/rules.py`, `coachfit/explain.py`
(prompt v2 text, detector patterns in `required_mentions`, appended sentences). Model
`openai/gpt-4o-mini`, temperature 0, via OpenRouter.

## Cases

25 NHANES rows from `data/nhanes_fatloss_800.xlsx`, valid input only, **never used** in any
earlier run, sample or tuning set (the exclusion list is computed from `eval/results/`).
Stratified by the first matching flag, seed 20261010:

| Stratum | n |
|---|---|
| below_kcal_floor | 5 |
| underweight_bmi | 3 |
| label_sensitive | 7 |
| below_bmr | 5 |
| no flag | 5 |

## Procedure — paired

For each case the model is called **once** with prompt v2. That raw note is version A.
Version B is the same note after the coverage guard. A and B differ only by the guard.
If the number guard rejects the raw note, both versions are the template; the case stays in.

## Blinding

The 50 notes are shuffled (seed 20261010) and numbered 1–50 with no version marker. The key
is written to `key.json`, which the grader does not open before grading is complete.
Known limit: guard-appended sentences have fixed wording and may be recognisable.

## Grading — by the author, per flag

For every note the sheet lists the flags the rules raised. For each flag the grader marks
**1 = stated** (the meaning is conveyed; exact wording not required) or **0 = not stated**.
Flags: deficit label; logging-error sensitivity; below safety floor; below BMR; BMI < 18.5;
coach review required (when floor or BMI applies).
Then one mark per note: **1 = nothing invented or contradictory**, **0 = the note asserts a flag
the rules did not raise, points the advice the wrong way for the label, or contradicts itself**.
A note **passes** when every flag is 1 and the invented/contradiction mark is 1.
Chinese translations are provided for reading; the English text is authoritative.

## Measures and pass criteria (fixed now)

| # | Measure | Pass if |
|---|---|---|
| H1 | Version B notes that pass | ≥ 24 / 25 |
| H2 | Detector recall: of flags the grader marked 0 in version A, the share the detector also flagged as missing | ≥ 95%; if fewer than 10 such flags exist, report the count, and pass only if none was missed |
| H3 | Version B notes with an invented flag or contradiction | 0 |

Also reported, with no pass line: version A pass rate; paired table (A pass/fail × B pass/fail);
omissions per flag type; detector false alarms (flags it called missing that the grader marked 1);
exact 95% confidence intervals (Clopper–Pearson) for H1 and the version A rate.

## Analysis

`eval/confirmatory.py analyze` — written and committed before grading. It reads the graded
sheet and `key.json` and prints the measures above. No other analysis is used for the headline.

## If a criterion fails

It is reported as failed, in the report and the video. The system is not changed and re-tested
on these cases.
