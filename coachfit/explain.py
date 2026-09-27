"""LLM layer: turns a rules Assessment into coach-facing prose.

The model never computes anything. It receives the finished numbers and is
only allowed to repeat them. `check_numbers` enforces that: any number in the
model's text that is not in the assessment makes us discard the model output
and fall back to a fixed template. The template is also what runs when there
is no API key, so the app always works.
"""
from __future__ import annotations

import json
import os
import re

from coachfit.rules import Assessment, ClientProfile, needs_human_review

MODEL = "openai/gpt-4o-mini"
PRICE_IN_PER_M = 0.15     # US$ per 1M input tokens (OpenRouter)
PRICE_OUT_PER_M = 0.60    # US$ per 1M output tokens
NUMBER_TOLERANCE = 1.0    # rounding slack when matching numbers

SYSTEM = """You write short notes for a gym coach about a fat-loss client.
You are given a JSON assessment that has ALREADY been calculated by a rules engine.

Rules:
- Use ONLY numbers that appear in the assessment or the client profile. Never calculate new numbers, never estimate.
- Do not change the labels. Explain them.
- If "needs_human_review" is true, say clearly that the coach should review this case before acting, and why.
- No medical diagnosis. No meal plans. Plain language a coach can read in 20 seconds.

Return ONLY a JSON object with exactly these fields:
{"summary": "<one sentence verdict>",
 "explanation": "<2-3 sentences: why, citing the numbers>",
 "next_step": "<one concrete action for the coach>"}"""

LABEL_TEXT = {
    "no_deficit": "is not in a calorie deficit",
    "too_small": "is in a deficit that is too small for meaningful fat loss",
    "appropriate": "is in an appropriate fat-loss deficit",
    "too_large": "is in a deficit that is too aggressive",
}
NEXT_STEP = {
    "no_deficit": "Review the food log with the client and agree a lower daily intake inside the target range.",
    "too_small": "Suggest a modest reduction so intake sits inside the target range.",
    "appropriate": "Keep the current intake and re-check body weight in two weeks.",
    "too_large": "Raise intake into the target range to protect training quality and adherence.",
}


def _get_key() -> str | None:
    return os.environ.get("OPENROUTER_API_KEY") or os.environ.get("MY_PRIVATE_OPENROUTER_KEY")


def allowed_numbers(p: ClientProfile, a: Assessment) -> list[float]:
    """Every number the model is permitted to mention."""
    nums: list[float] = []

    def add(x):
        if isinstance(x, (int, float)) and not isinstance(x, bool):
            nums.append(float(x))
        elif isinstance(x, (list, tuple)):
            for y in x:
                add(y)

    for v in vars(p).values():
        add(v)
    for v in a.to_dict().values():
        add(v)
    # Numbers that appear inside the rules' own reason strings (e.g. the 1200 kcal floor).
    for r in a.reasons:
        add([float(n) for n in re.findall(r"\d+(?:\.\d+)?", r)])
    add([0.5, 1, 2, 18.5, 1.6, 2.2])   # fixed constants of the method
    return nums


def check_numbers(text: str, allowed: list[float]) -> list[str]:
    """Return numbers in `text` that are not in `allowed` (empty list = pass)."""
    bad = []
    for raw in re.findall(r"\d[\d,]*(?:\.\d+)?", text):
        n = float(raw.replace(",", ""))
        if not any(abs(n - x) <= NUMBER_TOLERANCE for x in allowed):
            bad.append(raw)
    return bad


def template_explanation(p: ClientProfile, a: Assessment) -> dict:
    """Deterministic fallback. Also the no-LLM baseline for the evaluation."""
    if a.status == "abstain":
        return {
            "summary": "Cannot assess this client: the profile has a problem.",
            "explanation": "; ".join(a.reasons) + ".",
            "next_step": "Correct the client profile and run the check again.",
        }
    lo, hi = a.target_intake_range
    summary = f"The client {LABEL_TEXT[a.deficit_label]}."
    explanation = (
        f"Estimated maintenance (TDEE) is {a.tdee:.0f} kcal and the client eats "
        f"{p.daily_kcal:.0f} kcal, a deficit of {a.deficit:.0f} kcal. "
        f"The target intake for 0.5-1% weekly loss is {lo:.0f}-{hi:.0f} kcal.")
    if a.protein_label == "insufficient":
        explanation += (f" Protein is {a.protein_g_per_kg} g/kg, below the "
                        f"{a.protein_target_g[0]}-{a.protein_target_g[1]} g target.")
    next_step = NEXT_STEP[a.deficit_label]
    if needs_human_review(a):
        summary = "Coach review needed. " + summary
        next_step = "Review before acting: " + "; ".join(a.reasons) + "."
    return {"summary": summary, "explanation": explanation, "next_step": next_step}


def explain(p: ClientProfile, a: Assessment, client=None) -> dict:
    """Return {"summary","explanation","next_step","source","tokens_in","tokens_out","cost_usd","note"}.

    source is "llm" when the model output passed every check, otherwise "template".
    """
    base = template_explanation(p, a)
    meta = {"source": "template", "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "note": ""}

    # Abstentions never go to the model: there is nothing safe for it to explain.
    if a.status == "abstain":
        return {**base, **meta, "note": "abstained: invalid input"}

    if client is None:
        key = _get_key()
        if not key:
            return {**base, **meta, "note": "no API key: template used"}
        from openai import OpenAI
        client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)

    payload = {"client_profile": vars(p), "assessment": a.to_dict(),
               "needs_human_review": needs_human_review(a)}
    try:
        r = client.chat.completions.create(
            model=MODEL, temperature=0, max_tokens=300,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": SYSTEM},
                      {"role": "user", "content": json.dumps(payload)}])
        text = r.choices[0].message.content
        tin, tout = r.usage.prompt_tokens, r.usage.completion_tokens
    except Exception as e:  # network, quota, bad key
        return {**base, **meta, "note": f"API error, template used: {type(e).__name__}"}

    meta.update(tokens_in=tin, tokens_out=tout,
                cost_usd=(tin * PRICE_IN_PER_M + tout * PRICE_OUT_PER_M) / 1e6)

    try:
        out = json.loads(text)
        out = {k: str(out[k]) for k in ("summary", "explanation", "next_step")}
    except (json.JSONDecodeError, KeyError, TypeError):
        return {**base, **meta, "note": "LLM output was not valid JSON: template used"}

    bad = check_numbers(" ".join(out.values()), allowed_numbers(p, a))
    if bad:
        return {**base, **meta, "note": f"LLM invented numbers {bad}: template used"}

    if needs_human_review(a) and "review" not in (out["summary"] + out["next_step"]).lower():
        return {**base, **meta, "note": "LLM dropped the human-review warning: template used"}

    return {**out, **meta, "source": "llm"}
