# Evaluation

Every figure in the report comes from a file in this folder. This page says what each script
measures, where its output lives, and which runs are **exploratory** (they shaped the design)
versus **confirmatory** (the pre-registered test the headline result rests on).

## What is measured, and why

The rules (`coachfit/rules.py`) make every decision; the model only writes a note. So there are
two different questions, and they are evaluated separately:

1. **Is the arithmetic right?** Compare the rules with labels computed independently in Excel.
   This checks the implementation, not the model.
2. **Does the model's note say what the rules decided?** The headline metric, suggested by the
   instructor: *does the note state every flag the rules raised, and invent none?* — scored 0/1
   by hand. A model judge was tried and measured, and was not reliable enough to be the metric.

## Scripts

| Script | Measures | Writes | Cost |
|---|---|---|---|
| `run_eval.py` | A rules vs Excel · B LLM classifying directly · C logging-error sensitivity · D notes per prompt version (number guard, automatic flag check, model judge) · E safety routing | `results/` (latest run) | ~US$0.10; `--free` runs A and C only |
| `judge_agreement.py` | model judge vs a person's verdicts (precision / recall of FAIL) | `*_vs_judge.csv` next to the graded sheet | free |
| `heldout_v3.py` | exploratory held-out check of v3 on 20 new cases | `results/heldout_v3.jsonl` | <US$0.01 |
| `confirmatory.py` | **pre-registered paired blind test** of the coverage guard | `confirmatory/` | <US$0.01 |
| `cost_to_serve.py` | cost per successful check (Class 5 method), break-even reading time | `results/cost_to_serve.json` | free |

Inputs: `../data/nhanes_fatloss_800.xlsx` (see `../data/README.md`) and `handwritten_cases.csv`
(14 edge cases, expected outcomes fixed before any run).

## Run history

Runs were archived, never overwritten, so the design history can be checked.

| Folder | When | What changed before it | What it found |
|---|---|---|---|
| `results/run1_before_fixes/` | 27 Sep | first full run | guard rejected 42/226 notes — all false positives (regex read "−90" as 90); same-model judge unreliable |
| `results/run2_fixed_guard_and_judge/` | 27 Sep | sign bug fixed; judge → `deepseek-chat` | author hand-graded 20 judge verdicts: 75% agreement, FAIL precision 60%, recall 86%; "below BMR" flag made the model say "eat more" (4/10) |
| `results/run3_before_protein_removal/` | 27–28 Sep | below-BMR flag reworded; borderline review → ±10% label range | that error fell to 0/10; first flag-fidelity grading, v2: **10/20**, all omissions, six of them "protein not logged" |
| `results/` (top level) | 28 Sep | protein removed from scope; v3 coverage guard added | automatic flag check: v1 80%, v2 54%, v3 100% after guard; judge v1 87%, v2 97%, v3 94% |
| `results/heldout_v3.jsonl` | 28 Sep | — | 20 new cases, v3 graded unblinded: 20/20 (exploratory) |
| **`confirmatory/`** | **29 Sep** | **protocol committed before any data** | **guarded 25/25 (95% CI 86–100%); detector caught 16/16 omissions; 0 errors added; unguarded 10/25** |

Exploratory runs mixed scopes (protein in/out), case sets and an unblinded grader, so they cannot
compare v2 with v3. The confirmatory test was designed to fix exactly that.

## The confirmatory test (`confirmatory/`)

| File | What it is |
|---|---|
| `PREREGISTRATION.md` | protocol, sample, grading rules and pass lines — committed **before** generation |
| `DEVIATIONS.md` | the sheet was graded twice; which grading is primary, decided before reading it |
| `cases.jsonl` | 25 cases; for each, note A (model, prompt v2) and note B (same note + coverage guard) |
| `key.json` | which shuffled note number is which case and version (hidden from the grader) |
| `zh.json` | Chinese reading translations shown in the sheet (English is authoritative) |
| `盲评表_50条.xlsx` | the blank blind sheet |
| `盲评表_50条_第一次评分.xlsx`, `_第二次评分.xlsx`, `_第二次评分_转换.xlsx` | first grading; second grading as written; second grading converted to 1/0 |
| `grades.csv`, `results.json` | primary (second) grading and its analysis |
| `grades_first_grading.csv`, `results_first_grading.json` | first grading — same result; 172/172 marks agree |

Reproduce the analysis: `.venv/bin/python -m eval.confirmatory analyze eval/confirmatory/盲评表_50条_第二次评分_转换.xlsx`

## Where each report figure comes from

| Report figure | File |
|---|---|
| Rules vs Excel 787/787; 13 refused | `results/summary.json` → `A_rules_vs_excel` |
| LLM classifying directly 37–40%; ~1 in 5 near a boundary | `B_llm_only_baseline` in each run's `summary.json` |
| 48% of cases sensitive to ±10% logging error; threshold sweep (28% / 76% / 38%) | `results/summary.json` → `C_abstention` |
| 27/27 safety cases routed | `results/summary.json` → `D_explanations_v3.safety_review_shown_rate` |
| Judge 75% / 60% / 86% | `results/run2_fixed_guard_and_judge/human_check_vs_judge.csv` |
| Below-BMR "eat more" 4/10 → 0/10 | `appropriate_below_bmr_told_to_eat_more` in run 2 and run 3 summaries |
| v2 flag fidelity 10/20 | `results/run3_before_protein_removal/flag_fidelity_v2_hand.csv` |
| Guarded 25/25, unguarded 10/25, 16/16 caught, 0 added | `confirmatory/results.json` |
| Cost per successful check, 270 s / 62 s break-even | `cost_to_serve.py --success 0.40` / `--success 0.863` |

## Honest notes on grading

- Every hand grade is by the author, who also built the system. Chinese translations were provided
  for reading; ChatGPT was used once to translate material, never to grade.
- `run2_fixed_guard_and_judge/claude_check.csv` is an AI's (Claude's) grading, kept for
  comparison only; the reported judge figures use the author's `human_check.csv`.
- `run3_before_protein_removal/人工评分表_随机30条.xlsx` was superseded by the instructor's metric
  before it was graded; it is kept but not used.
