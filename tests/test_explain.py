"""Unit tests for coachfit/explain.py, using a fake model client (no API calls, no cost).

Covers the template fallback, the number guard (including the run-1 negative-number bug),
the review-warning check, pre-computed FACTS sentences, and the v3 flag-coverage guard.
"""
import json
from types import SimpleNamespace

from coachfit.explain import allowed_numbers, check_numbers, explain
from coachfit.rules import ClientProfile, assess


def profile(**overrides):
    base = dict(age=30, sex="male", height_cm=175, weight_kg=80,
                activity="moderate", daily_kcal=2200)
    base.update(overrides)
    return ClientProfile(**base)


class FakeClient:
    """Stands in for the OpenAI client so tests cost nothing."""

    def __init__(self, reply: dict | str):
        content = reply if isinstance(reply, str) else json.dumps(reply)
        resp = SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
            usage=SimpleNamespace(prompt_tokens=400, completion_tokens=80))
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **kw: resp))


def test_check_numbers():
    allowed = [2710.6, 2200, 510.6]
    assert check_numbers("TDEE 2,711 kcal, eats 2200, deficit 511", allowed) == []
    assert check_numbers("deficit of 650 kcal", allowed) == ["650"]


def test_no_key_uses_template(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.delenv("MY_PRIVATE_OPENROUTER_KEY", raising=False)
    out = explain(profile(), assess(profile()))
    assert out["source"] == "template"
    assert "appropriate" in out["summary"]


def test_good_llm_output_is_used():
    p = profile()
    reply = {"summary": "Intake is in an appropriate deficit.",
             "explanation": "TDEE is 2711 kcal and intake is 2200 kcal, a 511 kcal deficit.",
             "next_step": "Keep intake and re-weigh in 2 weeks."}
    out = explain(p, assess(p), client=FakeClient(reply))
    assert out["source"].startswith("llm")          # v3 may append a missing flag
    assert out["summary"] == reply["summary"]
    assert out["cost_usd"] > 0


def test_invented_number_falls_back():
    p = profile()
    reply = {"summary": "ok", "explanation": "Deficit is about 650 kcal.", "next_step": "keep"}
    out = explain(p, assess(p), client=FakeClient(reply))
    assert out["source"] == "template"
    assert "650" in out["note"]


def test_dropped_review_warning_falls_back():
    p = profile(sex="female", weight_kg=60, height_cm=165, daily_kcal=1000)
    reply = {"summary": "Great progress.", "explanation": "Eats 1000 kcal.", "next_step": "Keep going."}
    out = explain(p, assess(p), client=FakeClient(reply))
    assert out["source"] == "template"


def test_bad_json_falls_back():
    p = profile()
    out = explain(p, assess(p), client=FakeClient("Sure! Here is the note..."))
    assert out["source"] == "template"


def test_abstain_never_calls_model():
    p = profile(height_cm=17.5)
    out = explain(p, assess(p), client=FakeClient({"summary": "x"}))
    assert out["source"] == "template"
    assert out["tokens_in"] == 0


def test_allowed_numbers_include_reason_constants():
    p = profile(sex="female", weight_kg=60, height_cm=165, daily_kcal=1000)
    assert 1200 in allowed_numbers(p, assess(p))


def test_facts_state_comparisons():
    from coachfit.explain import facts
    p = profile()
    f = " ".join(facts(p, assess(p)))
    assert "Daily intake 2200 kcal is within the target intake range 1831-2271 kcal" in f


def test_negative_deficit_is_not_invented():
    # Run 1 regression: "-90 kcal" was read as 90 and rejected.
    assert check_numbers("a deficit of -90.2 kcal, a surplus of 90 kcal", [-90.2]) == []


def test_surplus_fact_wording():
    from coachfit.explain import facts
    p = profile(daily_kcal=2800)
    assert "MORE than maintenance" in " ".join(facts(p, assess(p)))


def test_v3_guard_appends_missing_sensitivity_flag():
    # 2200 kcal is label-sensitive; this note never mentions logging error.
    p = profile()
    reply = {"summary": "Intake is appropriate for fat loss.",
             "explanation": "TDEE is 2711 kcal and intake is 2200 kcal.",
             "next_step": "Keep going."}
    out = explain(p, assess(p), client=FakeClient(reply), prompt="v3")
    assert out["source"] == "llm+guard"
    assert out["missing_flags_raw"] == ["label_sensitive"]
    assert "could be too_small or appropriate" in out["explanation"]


def test_v2_reports_missing_but_does_not_add():
    p = profile()
    reply = {"summary": "Intake is appropriate.", "explanation": "Eats 2200 kcal.", "next_step": "Keep going."}
    out = explain(p, assess(p), client=FakeClient(reply), prompt="v2")
    assert out["source"] == "llm" and out["missing_flags_raw"] == ["label_sensitive"]


def test_safety_flags_are_required_mentions():
    from coachfit.explain import missing_flags
    p = profile(sex="female", weight_kg=60, height_cm=165, daily_kcal=1000)
    note = {"summary": "Coach review needed: deficit too large.", "explanation": "Eats 1000 kcal.",
            "next_step": "Review."}
    assert set(missing_flags(p, assess(p), note)) == {"below_kcal_floor", "below_bmr"}
