# CoachFit Cut Assistant

Tells a gym coach whether a client's daily calorie intake is a sensible fat-loss deficit — and
hands the case to the coach when it is not safe to answer alone.

PE6201 · Emerging AI Technologies · End-of-Course Project · LIU ZEYUAN (Section B)

## Design in one line

**Rules decide; the model only explains; code checks the explanation.**
Asked to classify directly, `gpt-4o-mini` was right 37–40% of the time (majority baseline 25%),
so no number or verdict the coach sees comes from a model.

```
client profile ─► rules (coachfit/rules.py) ─► gpt-4o-mini note ─► guards (coachfit/explain.py) ─► coach
                  BMR · TDEE · label ·          explanation only     • unknown number → template
                  safety flags · ±10% range                          • missing flag  → appended
```

## Results (all measured, `eval/results/`)

| Check | Result |
|---|---|
| Rules vs labels computed independently in Excel (787 NHANES rows) | 787/787; 13 impossible rows refused |
| LLM classifying directly, formula in prompt (100 cases, 4 runs) | 37–40% |
| **Flag fidelity, hand-graded 0/1** — note states every flag, invents none | v2 10/20 → **v3 20/20 on 20 held-out cases** |
| Model judge vs author's hand labels (20) | 75% agreement · FAIL precision 60% · recall 86% |
| Safety cases routed to the coach | 27/27 |
| Cost | US$0.00014 and ~2 s per note; all evaluation US$0.30 |

The full argument is in [docs/tradeoff_analysis.md](docs/tradeoff_analysis.md).

## Run it

Needs Python 3.10+.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q                 # 24 tests, no API key needed
.venv/bin/streamlit run app.py                # the coach-facing app
```

Without an API key the app still works: every note comes from the fixed template, with identical
numbers. To use the model, put an [OpenRouter](https://openrouter.ai) key in
`.streamlit/secrets.toml` (git-ignored):

```toml
OPENROUTER_API_KEY = "sk-or-..."
```

Re-running the evaluation costs about US$0.10:

```bash
OPENROUTER_API_KEY=sk-or-... .venv/bin/python -m eval.run_eval        # parts A–E
.venv/bin/python -m eval.run_eval --free                              # free parts only
.venv/bin/python -m eval.cost_to_serve --success 1.0                  # Class 5 cost model
```

## Repository layout

| Path | What it is |
|---|---|
| `coachfit/rules.py` | Deterministic checks: BMR, TDEE, deficit label, safety flags, ±10% label range, abstention |
| `coachfit/explain.py` | LLM note (prompts v1–v3), number guard, flag-coverage guard, template fallback |
| `app.py` | Streamlit interface |
| `tests/` | Unit tests for rules and guards (fake model client, no API calls) |
| `data/nhanes_fatloss_800.xlsx` | 800 NHANES adults aged 20–35 prepared in A1 (public domain) |
| `eval/handwritten_cases.csv` | 14 edge cases with expected outcomes fixed before any run |
| `eval/run_eval.py` | Evaluation parts A–E |
| `eval/heldout_v3.py` | 20 held-out cases for the final hand-graded test |
| `eval/cost_to_serve.py` | Cost per successful check (Class 5 method) |
| `eval/judge_agreement.py` | Model judge vs hand labels |
| `eval/results/` | Every run's raw outputs; `run1`–`run3` folders are archived earlier runs |
| `docs/` | Problem statement, trade-off analysis |

## Scope and responsible use

Coach decision support for healthy adults. Not medical advice; clients under 18 are refused.
Out of scope: meal plans, macronutrient targets (protein was removed because the evaluation data
has no protein column), and free-text food logs. No names or identifiers are sent to the model.

*Tools: Claude (Anthropic) helped write the code and draft the documents; ChatGPT translated
evaluation material for reading.*
