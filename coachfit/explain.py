"""LLM layer: turns a rules Assessment into a short coach-facing note.

The model never computes anything. It receives the finished numbers and only rephrases them.
Three prompt versions are kept so the evaluation can compare them:

- v1 — assessment JSON only.
- v2 — adds pre-computed FACTS sentences, so every comparison ("within", "above") is decided
       by code, not by the model.
- v3 — the v2 prompt plus a coverage guard (default): `missing_flags` checks the note against
       every flag the rules raised and appends a fixed sentence for each one left out.

Guards that apply to every version:
- `check_numbers` — any number not in the assessment rejects the note.
- the review check — a case that needs a coach must say "review".
A rejected note is replaced by `template_explanation`, which also runs when no API key is set,
so the app always works and always shows the same numbers.
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

# v2 adds one thing: pre-computed FACTS sentences, so the model never has to compare
# two numbers itself. v1 wrote "150 g is above the 128-176 g target" (it is inside).
SYSTEM_V2 = SYSTEM.replace(
    "- Do not change the labels. Explain them.",
    "- Do not change the labels. Explain them.\n"
    "- The input contains FACTS: sentences that already state every comparison (above / below / within). "
    "When you say whether something is above, below or within a range, copy it from FACTS. "
    "Never compare two numbers yourself.")
# v3 keeps the v2 prompt and adds one deterministic step: a coverage guard that
# appends any flag the note left out (hand grading of v2: 10/20 notes missed a flag,
# none invented one).
PROMPTS = {"v1": SYSTEM, "v2": SYSTEM_V2, "v3": SYSTEM_V2}
DEFAULT_PROMPT = "v3"

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
    add([0.5, 1, 2, 10, 18.5])   # fixed constants of the method
    return nums


def check_numbers(text: str, allowed: list[float]) -> list[str]:
    """Return numbers in `text` that are not in `allowed` (empty list = pass).

    Signs are ignored: "a deficit of -90 kcal" and "a surplus of 90 kcal" are the same fact.
    (Run 1 of the evaluation showed every rejection was this false positive.)
    """
    bad = []
    for raw in re.findall(r"\d[\d,]*(?:\.\d+)?", text):
        n = float(raw.replace(",", ""))
        if not any(abs(n - abs(x)) <= NUMBER_TOLERANCE for x in allowed):
            bad.append(raw)
    return bad


def _position(x: float, lo: float, hi: float) -> str:
    return "below" if x < lo else "above" if x > hi else "within"


def facts(p: ClientProfile, a: Assessment) -> list[str]:
    """Every comparison the note might make, decided by code rather than the model."""
    if a.status == "abstain":
        return []
    lo, hi = a.target_intake_range
    dlo, dhi = a.target_deficit_range
    out = [
        f"Daily intake {p.daily_kcal:.0f} kcal is {_position(p.daily_kcal, lo, hi)} "
        f"the target intake range {lo:.0f}-{hi:.0f} kcal.",
    ]
    if a.deficit <= 0:
        out.append(f"The client eats {-a.deficit:.0f} kcal MORE than maintenance ({a.tdee:.0f} kcal): "
                   f"a surplus, so there is no deficit and the label is no_deficit. "
                   f"The right direction is to eat less.")
    else:
        out.append(f"The client eats {a.deficit:.0f} kcal less than maintenance ({a.tdee:.0f} kcal); "
                   f"the target deficit is {dlo:.0f}-{dhi:.0f} kcal; so the label is {a.deficit_label}.")
    out += [r[0].upper() + r[1:] + "." for r in a.reasons]
    return out


# Each flag the rules can raise: how to recognise it in a note, and the sentence
# the guard appends when it is missing. Patterns are deliberately loose: a false
# "missing" only adds a redundant sentence, a false "present" would hide a flag.
LABEL_PATTERNS = {
    "no_deficit": r"surplus|no (caloric |calorie )?deficit|not in (a )?(caloric |calorie )?deficit"
                  r"|more than (their )?maintenance|no_deficit",
    "too_small": r"too small|too_small|small(er)? (caloric |calorie )?deficit|not (in )?an adequate",
    # "appropriate" alone is not enough: "fat loss is not an appropriate goal" (case S3).
    "appropriate": r"appropriate (caloric |calorie |fat.loss )?(deficit|intake)|deficit (is |label (is )?)?"
                   r"'?appropriate|label is appropriate|(is|appears|looks|seems) appropriate|on track",
    "too_large": r"too large|too_large|too aggressive|excessive|too big|larger than the target"
                 r"|(large|significant) (caloric |calorie )?deficit",
}
# Tuned on the 20 hand-graded v2 notes (development set); judged on a fresh 20.


def required_mentions(p: ClientProfile, a: Assessment) -> list[tuple[str, str, str]]:
    """(flag, regex that shows it was mentioned, sentence to append if not)."""
    if a.status == "abstain":
        return []
    req = [("label:" + a.deficit_label, LABEL_PATTERNS[a.deficit_label],
            f"Verdict: the client {LABEL_TEXT[a.deficit_label]}.")]
    reason = {f: r for f, r in zip(_flag_order(a), a.reasons)}
    if "label_sensitive" in a.flags:
        req.append(("label_sensitive", r"10 ?%|could be|confidence|uncertain|logging (error|accura|practice)|(food|intake) log"
                    r"|accura\w* (in |of )?(the )?(logg|track)|accurate tracking",
                    "Intake logs are often 10% off; within that error the label could be "
                    + " or ".join(a.possible_labels) + ", so check the food log before changing the plan."))
    if "below_kcal_floor" in a.flags:
        req.append(("below_kcal_floor", r"floor|minimum|1,?200|1,?500", reason["below_kcal_floor"]))
    if "below_bmr" in a.flags:
        req.append(("below_bmr", r"\bBMR\b|basal", reason["below_bmr"]))
    if "underweight_bmi" in a.flags:
        req.append(("underweight_bmi", r"underweight|BMI", reason["underweight_bmi"]))
    return req


def _flag_order(a: Assessment) -> list[str]:
    """a.reasons is written in the same order as the reason-carrying flags."""
    return [f for f in a.flags if f in ("label_sensitive", "below_kcal_floor", "below_bmr",
                                         "underweight_bmi")]


def missing_flags(p: ClientProfile, a: Assessment, note: dict) -> list[str]:
    text = " ".join(note.values())
    return [flag for flag, pat, _ in required_mentions(p, a) if not re.search(pat, text, re.I)]


def template_explanation(p: ClientProfile, a: Assessment) -> dict:
    """Deterministic fallback. Also the no-LLM baseline for the evaluation."""
    if a.status == "abstain":
        return {
            "summary": "Coach review needed: cannot assess this client because the profile has a problem.",
            "explanation": "; ".join(a.reasons) + ".",
            "next_step": "Correct the client profile and run the check again.",
        }
    lo, hi = a.target_intake_range
    summary = f"The client {LABEL_TEXT[a.deficit_label]}."
    explanation = (
        f"Estimated maintenance (TDEE) is {a.tdee:.0f} kcal and the client eats "
        f"{p.daily_kcal:.0f} kcal, a deficit of {a.deficit:.0f} kcal. "
        f"The target intake for 0.5-1% weekly loss is {lo:.0f}-{hi:.0f} kcal.")
    if a.confidence == "low":
        explanation += (" Intake logs are often 10% off; within that error the label could be "
                        + " or ".join(a.possible_labels) + ".")
    next_step = NEXT_STEP[a.deficit_label]
    if needs_human_review(a):
        summary = "Coach review needed. " + summary
        next_step = "Review before acting: " + "; ".join(a.reasons) + "."
    return {"summary": summary, "explanation": explanation, "next_step": next_step}


def explain(p: ClientProfile, a: Assessment, client=None, prompt: str = DEFAULT_PROMPT) -> dict:
    """Return {"summary","explanation","next_step","source","tokens_in","tokens_out","cost_usd","note"}.

    source is "llm" when the model output passed every check, otherwise "template".
    """
    base = template_explanation(p, a)
    # llm_output keeps what the model wrote even when it is rejected, for the evaluation.
    meta = {"source": "template", "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0, "note": "",
            "llm_output": None, "missing_flags_raw": []}

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
    if prompt in ("v2", "v3"):
        payload["FACTS"] = facts(p, a)
    try:
        r = client.chat.completions.create(
            model=MODEL, temperature=0, max_tokens=300,
            response_format={"type": "json_object"},
            messages=[{"role": "system", "content": PROMPTS[prompt]},
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
    meta["llm_output"] = out

    bad = check_numbers(" ".join(out.values()), allowed_numbers(p, a))
    if bad:
        return {**base, **meta, "note": f"LLM invented numbers {bad}: template used"}

    if needs_human_review(a) and "review" not in (out["summary"] + out["next_step"]).lower():
        return {**base, **meta, "note": "LLM dropped the human-review warning: template used"}

    meta["missing_flags_raw"] = missing_flags(p, a, out)
    if prompt == "v3" and meta["missing_flags_raw"]:
        add = [s for f, _, s in required_mentions(p, a) if f in meta["missing_flags_raw"]]
        out["explanation"] = out["explanation"].rstrip() + " " + " ".join(
            x[0].upper() + x[1:].rstrip(".") + "." for x in add)
        return {**out, **meta, "source": "llm+guard",
                "note": f"guard added missing flags {meta['missing_flags_raw']}"}
    return {**out, **meta, "source": "llm"}
