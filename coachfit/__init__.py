"""CoachFit Cut Assistant — the product code.

Two modules, one direction of data flow:

    ClientProfile ──► rules.assess() ──► Assessment ──► explain.explain() ──► coach note
                      (all arithmetic,                  (LLM writes prose; two guards
                       labels, safety flags)             check it; template fallback)

- `rules.py`   — deterministic: BMR, TDEE, deficit label, ±10% label range, safety flags,
                 abstention on invalid input. No model calls. Every number shown comes from here.
- `explain.py` — the only place a model is called (`openai/gpt-4o-mini` via OpenRouter).
                 Number guard: any number not produced by the rules → fixed template.
                 Coverage guard (v3): any flag the note leaves out → appended by code.

The Streamlit interface is `app.py` at the repository root; evaluation lives in `eval/`.
"""
