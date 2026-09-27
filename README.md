# CoachFit Cut Assistant

A decision-support tool that tells a gym coach whether a client's fat-loss intake is in a sensible
calorie deficit and whether protein is high enough — and hands the case to a human when it is not sure.

PE6201 · Emerging AI Technologies · End-of-Course Project · LIU ZEYUAN

> Work in progress. Sections marked TODO are filled in as the build proceeds.

## Design in one line

Rules do the arithmetic; the LLM only explains. In A1 Part 1 a foundation model scored 30.7% on this
exact classification task (majority baseline 29.8%), so no number the coach sees comes from a model.

## Repository layout

| Path | What it is |
|---|---|
| `coachfit/rules.py` | Deterministic checks: BMR, TDEE, deficit label, protein, safety flags, abstention |
| `tests/test_rules.py` | Unit tests for the rules, checked against hand calculations |
| `coachfit/explain.py` | TODO — LLM layer that turns the rule result into coach-facing advice |
| `app.py` | TODO — Streamlit interface |
| `data/` | TODO — client cases |
| `eval/` | TODO — evaluation set, baseline, results |
| `docs/` | TODO — problem statement, trade-off analysis, video script |

## Run it

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q
```
