import json
from types import SimpleNamespace

from coachfit.explain import allowed_numbers, check_numbers, explain
from coachfit.rules import ClientProfile, assess


def profile(**overrides):
    base = dict(age=30, sex="male", height_cm=175, weight_kg=80,
                activity="moderate", daily_kcal=2200, protein_g=150)
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
    assert out["source"] == "llm"
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
