"""Evaluation for CoachFit Cut Assistant.

    .venv/bin/python -m eval.run_eval            # everything (~US$0.10)
    .venv/bin/python -m eval.run_eval --free     # parts A and C only, no API calls

A  rules vs the labels computed in Excel for A1 (implementation check), all 800 NHANES rows
B  LLM-only baseline: the model classifies the deficit itself (what the design avoids)
C  logging-error sensitivity: how often would a 10% logging error change the label, and
   why a fixed "abstain within N kcal of a boundary" rule was dropped for a label range
D  explanation quality, prompt v1 vs v2: L1 automatic checks, L2 model judge
E  safety: every case that needs a human is routed to one

Raw outputs go to eval/results/, the summary to eval/results/summary.json.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd

from coachfit import explain as ex
from coachfit.rules import (DEFICIT_LABELS, LOGGING_ERROR, ClientProfile, assess,
                            needs_human_review)

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
NHANES = Path(os.environ.get("NHANES_XLSX", ROOT.parent / "data" / "nhanes_fatloss_800.xlsx"))
SEED = 42
N_PER_LABEL = 25          # NHANES sample for the paid parts: 25 per label = 100 cases
WORKERS = 4

LABEL_ZH = {"没有热量缺口": "no_deficit", "缺口过小": "too_small",
            "缺口合适": "appropriate", "缺口过大": "too_large"}
ACTIVITY = {"sedentary": "sedentary", "low": "light", "moderate": "moderate", "high": "active"}


# ---------------------------------------------------------------- data

def load_nhanes() -> pd.DataFrame:
    df = pd.read_excel(NHANES)
    df["label_en"] = df["label"].map(LABEL_ZH)
    df["activity_en"] = df["activity_level"].map(ACTIVITY)
    return df


def nhanes_profile(r) -> ClientProfile:
    return ClientProfile(age=int(r.age_years), sex=r.sex, height_cm=float(r.height_cm),
                         weight_kg=float(r.weight_kg), activity=r.activity_en,
                         daily_kcal=float(r.daily_kcal))


def load_handwritten() -> pd.DataFrame:
    return pd.read_csv(ROOT / "handwritten_cases.csv")


def hand_profile(r) -> ClientProfile:
    return ClientProfile(age=int(r.age), sex=r.sex, height_cm=float(r.height_cm),
                         weight_kg=float(r.weight_kg), activity=r.activity,
                         daily_kcal=float(r.daily_kcal))


def sample_nhanes(df: pd.DataFrame) -> pd.DataFrame:
    valid = df[[assess(nhanes_profile(r)).status == "ok" for r in df.itertuples()]]
    return pd.concat([valid[valid.label_en == lab].sample(N_PER_LABEL, random_state=SEED)
                      for lab in DEFICIT_LABELS]).reset_index(drop=True)


def client():
    key = ex._get_key()
    if not key:
        raise SystemExit("Set OPENROUTER_API_KEY (or run with --free).")
    from openai import OpenAI
    # Shared upstream pools rate-limit (429) under load; the client backs off and retries.
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key, max_retries=8)


def pmap(fn, items):
    with ThreadPoolExecutor(WORKERS) as pool:
        return list(pool.map(fn, items))


# ---------------------------------------------------------------- A

def part_a(df):
    rows = []
    for r in df.itertuples():
        a = assess(nhanes_profile(r))
        rows.append({"participant_id": r.participant_id, "excel_label": r.label_en,
                     "status": a.status, "rules_label": a.deficit_label,
                     "reasons": "; ".join(a.reasons) if a.status == "abstain" else ""})
    out = pd.DataFrame(rows)
    ok = out[out.status == "ok"]
    return out, {
        "rows": len(out),
        "abstained_invalid_input": int((out.status == "abstain").sum()),
        "abstain_examples": out[out.status == "abstain"].reasons.head(5).tolist(),
        "agreement_on_valid_rows": round(float((ok.excel_label == ok.rules_label).mean()), 4),
        "disagreements": int((ok.excel_label != ok.rules_label).sum()),
    }


# ---------------------------------------------------------------- B

BASELINE_SYSTEM = f"""You classify a fat-loss client's daily calorie intake.
Method:
- BMR (Mifflin-St Jeor): male 10*kg + 6.25*cm - 5*age + 5; female 10*kg + 6.25*cm - 5*age - 161
- TDEE = BMR * activity factor (sedentary 1.2, light 1.375, moderate 1.55, active 1.725, very_active 1.9)
- deficit = TDEE - intake
- target deficit per day = body weight * (0.5% to 1%) * 7700 / 7
Labels: no_deficit (deficit <= 0), too_small (below target), appropriate (inside target), too_large (above target).
Reply with exactly one word from: {", ".join(DEFICIT_LABELS)}."""


def part_b(sample, llm):
    def run(r):
        p = nhanes_profile(r)
        t0 = time.time()
        resp = llm.chat.completions.create(
            model=ex.MODEL, temperature=0, max_tokens=10,
            messages=[{"role": "system", "content": BASELINE_SYSTEM},
                      {"role": "user", "content": json.dumps(vars(p))}])
        text = resp.choices[0].message.content.strip().lower()
        pred = next((l for l in DEFICIT_LABELS if l in text), "unparsable")
        a = assess(p)
        return {"participant_id": r.participant_id, "truth": r.label_en, "llm": pred, "raw": text,
                "label_sensitive": a.confidence == "low",
                "boundary_distance": round(min(abs(a.deficit - b) for b in
                                               (0, *a.target_deficit_range)), 1),
                "latency_s": round(time.time() - t0, 2),
                "tokens_in": resp.usage.prompt_tokens, "tokens_out": resp.usage.completion_tokens}

    out = pd.DataFrame(pmap(run, list(sample.itertuples())))
    out["correct"] = out.truth == out.llm
    near = out[out.boundary_distance < 100]
    far = out[out.boundary_distance >= 100]
    cost = (out.tokens_in.sum() * ex.PRICE_IN_PER_M + out.tokens_out.sum() * ex.PRICE_OUT_PER_M) / 1e6
    return out, {
        "cases": len(out),
        "llm_only_accuracy": round(float(out.correct.mean()), 4),
        "rules_accuracy": 1.0,
        "majority_baseline": round(float(out.truth.value_counts(normalize=True).max()), 4),
        "accuracy_within_100kcal_of_boundary": round(float(near.correct.mean()), 4) if len(near) else None,
        "n_within_100kcal": len(near),
        "accuracy_further_than_100kcal": round(float(far.correct.mean()), 4) if len(far) else None,
        "n_further": len(far),
        "unparsable": int((out.llm == "unparsable").sum()),
        "median_latency_s": float(out.latency_s.median()),
        "cost_usd": round(cost, 5),
        "confusion": pd.crosstab(out.truth, out.llm).to_dict(),
    }


# ---------------------------------------------------------------- C

def part_c(df, error=LOGGING_ERROR, thresholds=(25, 50, 100, 150, 200)):
    """A case is 'unstable' if moving intake by +-error flips the label.

    Self-reported intake is commonly off by 10% or more, so +-10% is a mild assumption.
    """
    recs = []
    for r in df.itertuples():
        p = nhanes_profile(r)
        a = assess(p)
        if a.status != "ok":
            continue
        labels = {assess(ClientProfile(**{**vars(p), "daily_kcal": p.daily_kcal * f})).deficit_label
                  for f in (1 - error, 1 + error)}
        dist = min(abs(a.deficit - b) for b in (0, *a.target_deficit_range))
        recs.append({"unstable": labels != {a.deficit_label}, "distance": dist,
                     "range_size": len(a.possible_labels)})
    d = pd.DataFrame(recs)
    rows = []
    for t in thresholds:
        flagged = d.distance < t
        tp = int((flagged & d.unstable).sum())
        rows.append({
            "threshold_kcal": t,
            "abstain_rate": round(float(flagged.mean()), 4),
            "precision": round(tp / max(int(flagged.sum()), 1), 4),
            "recall": round(tp / max(int(d.unstable.sum()), 1), 4),
        })
    return {"logging_error_assumed": error, "valid_rows": len(d),
            "unstable_rate": round(float(d.unstable.mean()), 4),
            "shown_as_label_range_rate": round(float((d.range_size > 1).mean()), 4),
            "range_size_counts": d.range_size.value_counts().sort_index().to_dict(),
            "rejected_design_abstain_within_n_kcal": rows}


# ---------------------------------------------------------------- D + E

# Run 1 used gpt-4o-mini as its own judge and it misread negative deficits
# ("eats more than maintenance, so eat less" marked FAIL). Run 2 uses a model
# from another vendor and states what the labels mean.
JUDGE_MODEL = "deepseek/deepseek-chat"
JUDGE_PRICE_IN_PER_M, JUDGE_PRICE_OUT_PER_M = 0.32, 0.89

JUDGE_SYSTEM = """You check a short note written for a gym coach about a fat-loss client.
You get FACTS (ground truth, computed by code) and the NOTE.

What the labels mean:
- no_deficit: the client eats at or above maintenance (a surplus). Correct advice is to eat LESS.
- too_small: a deficit exists but is smaller than the target. Correct advice is a modest reduction.
- appropriate: the deficit is inside the target. Correct advice is to keep going.
- too_large: the deficit is bigger than the target. Correct advice is to eat MORE.
A "deficit of -90 kcal" and "a surplus of 90 kcal" mean the same thing.

FAIL the note if ANY of these is true:
- it states a fact that contradicts FACTS (wrong number, or above/below/within stated wrongly)
- its verdict or advice points the wrong way for the label
- FACTS say human review is required and the note does not tell the coach to review
Otherwise PASS. Style, length and wording do not matter.
Return ONLY JSON: {"verdict": "PASS" or "FAIL", "reason": "<one short sentence>"}"""


def judge(llm, fact_list, note):
    text = f"FACTS:\n- " + "\n- ".join(fact_list) + f"\n\nNOTE:\n{json.dumps(note)}"
    for attempt in range(5):
        r = llm.chat.completions.create(
            model=JUDGE_MODEL, temperature=0, max_tokens=120,
            messages=[{"role": "system", "content": JUDGE_SYSTEM}, {"role": "user", "content": text}])
        if r.choices:            # an overloaded upstream sometimes returns an empty body
            break
        time.sleep(2 ** attempt)
    else:
        return "ERROR", "judge returned no answer after 5 attempts", r.usage
    content = r.choices[0].message.content or ""
    m = re.search(r"\{.*\}", content, re.S)
    try:
        j = json.loads(m.group(0)) if m else {}
        v = "PASS" if str(j.get("verdict", "")).upper() == "PASS" else "FAIL"
        return v, str(j.get("reason", "judge output unparsable")), r.usage
    except json.JSONDecodeError:
        return "FAIL", "judge output unparsable", r.usage


def part_d(cases, llm, prompt):
    def run(c):
        cid, group, p = c
        a = assess(p)
        t0 = time.time()
        out = ex.explain(p, a, client=llm, prompt=prompt)
        latency = time.time() - t0
        f = ex.facts(p, a)
        if needs_human_review(a) and a.status == "ok":
            f = f + ["This case requires human review by the coach."]
        rec = {"case_id": cid, "group": group, "prompt": prompt, "status": a.status,
               "needs_review": needs_human_review(a), "source": out["source"],
               "guard_note": out["note"], "latency_s": round(latency, 2),
               "cost_usd": out["cost_usd"], "facts": f,
               "llm_output": out["llm_output"],
               "shown": {k: out[k] for k in ("summary", "explanation", "next_step")},
               "missing_flags_raw": out.get("missing_flags_raw", []),
               "missing_flags_final": ex.missing_flags(p, a, {k: out[k] for k in
                                                              ("summary", "explanation", "next_step")})}
        judge_cost = 0.0
        if out["llm_output"] is not None:
            v, why, u = judge(llm, f, out["llm_output"])
            rec["judge_raw"], rec["judge_raw_reason"] = v, why
            if u is not None:
                judge_cost += (u.prompt_tokens * JUDGE_PRICE_IN_PER_M
                               + u.completion_tokens * JUDGE_PRICE_OUT_PER_M) / 1e6
        text = " ".join(rec["shown"].values()).lower()
        rec["shown_mentions_review"] = "review" in text
        rec["judge_cost_usd"] = judge_cost
        return rec

    recs = pmap(run, cases)
    d = pd.DataFrame(recs)
    called_ = d[d.llm_output.notna()]
    auto_raw = float((called_.missing_flags_raw.str.len() == 0).mean())
    auto_final = float((called_.missing_flags_final.str.len() == 0).mean())
    called = d[d.llm_output.notna()]
    fell_back = called[called.source == "template"]
    judged = called[called.judge_raw != "ERROR"]
    review = d[d.needs_review]
    return recs, {
        "prompt": prompt,
        "cases": len(d),
        "sent_to_llm": len(called),
        "L1_pass_rate": round(float(called.source.str.startswith("llm").mean()), 4),
        "auto_all_flags_stated_raw_llm": round(auto_raw, 4),
        "auto_all_flags_stated_shown": round(auto_final, 4),
        "guard_added_flags": int((called.source == "llm+guard").sum()),
        "L1_fallback_reasons": fell_back.guard_note.str.replace(r"\[.*\]", "[...]", regex=True)
                                         .value_counts().to_dict(),
        "L2_judge_pass_rate_raw_llm": round(float((judged.judge_raw == "PASS").mean()), 4),
        "judge_errors_excluded": int((called.judge_raw == "ERROR").sum()),
        "L2_fail_examples": called[called.judge_raw == "FAIL"][["case_id", "judge_raw_reason"]]
                              .head(8).to_dict("records"),
        "safety_cases_needing_review": len(review),
        "safety_review_shown_rate": round(float(review.shown_mentions_review.mean()), 4),
        "mean_latency_s": round(float(d.latency_s.mean()), 2),
        "explain_cost_usd": round(float(d.cost_usd.sum()), 5),
        "judge_cost_usd": round(float(d.judge_cost_usd.sum()), 5),
        "cost_per_explained_case_usd": round(float(called.cost_usd.mean()), 6),
    }


EAT_MORE = re.compile(r"increas\w* (their |her |his |the client.s )?(daily )?(caloric |calorie )?intake"
                      r"|eat more", re.I)


def eat_more_check(recs, prompt):
    """Deterministic L2 check for the run-2 failure: an 'appropriate' client below BMR
    being told to eat more. No judge involved."""
    hits = [r for r in recs if r["prompt"] == prompt and r["llm_output"]
            and any("below estimated BMR" in f for f in r["facts"])
            and any("label is appropriate" in f for f in r["facts"])]
    bad = [r["case_id"] for r in hits if EAT_MORE.search(" ".join(r["llm_output"].values()))]
    return {"cases": len(hits), "told_to_eat_more": len(bad), "case_ids": bad}


def human_check_sheet(recs, n=20):
    """Sheet for a person to grade, judge verdicts hidden. Key kept separately."""
    rng = random.Random(SEED)
    judged = [r for r in recs if "judge_raw" in r]
    fails = [r for r in judged if r["judge_raw"] == "FAIL"]
    passes = [r for r in judged if r["judge_raw"] == "PASS"]
    pick = rng.sample(fails, min(len(fails), n // 2))
    pick += rng.sample(passes, min(len(passes), n - len(pick)))
    rng.shuffle(pick)
    sheet = pd.DataFrame([{"item": i + 1, "case_id": r["case_id"], "prompt": r["prompt"],
                           "facts": "\n".join(r["facts"]),
                           "note": "\n".join(r["llm_output"].values()),
                           "your_verdict (PASS/FAIL)": "", "your_reason": ""}
                          for i, r in enumerate(pick)])
    key = pd.DataFrame([{"item": i + 1, "judge": r["judge_raw"], "judge_reason": r["judge_raw_reason"]}
                        for i, r in enumerate(pick)])
    return sheet, key


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--free", action="store_true", help="only the parts that cost nothing")
    args = ap.parse_args()
    RESULTS.mkdir(exist_ok=True)

    df = load_nhanes()
    summary = {}

    a_rows, summary["A_rules_vs_excel"] = part_a(df)
    a_rows.to_csv(RESULTS / "A_rules_vs_excel.csv", index=False)
    summary["C_abstention"] = part_c(df)

    if not args.free:
        llm = client()
        sample = sample_nhanes(df)
        sample[["participant_id", "label_en"]].to_csv(RESULTS / "nhanes_sample_ids.csv", index=False)

        b_rows, summary["B_llm_only_baseline"] = part_b(sample, llm)
        b_rows.to_csv(RESULTS / "B_llm_only_baseline.csv", index=False)

        hand = load_handwritten()
        cases = ([(f"N{r.participant_id}", "nhanes", nhanes_profile(r)) for r in sample.itertuples()]
                 + [(r.case_id, r.group, hand_profile(r)) for r in hand.itertuples()])
        all_recs = []
        for prompt in ("v1", "v2", "v3"):
            recs, summary[f"D_explanations_{prompt}"] = part_d(cases, llm, prompt)
            summary[f"D_explanations_{prompt}"]["appropriate_below_bmr_told_to_eat_more"] = \
                eat_more_check(recs, prompt)
            all_recs += recs
        (RESULTS / "D_explanations.jsonl").write_text(
            "\n".join(json.dumps(r, default=str) for r in all_recs))

        sheet, key = human_check_sheet(all_recs)
        sheet.to_csv(RESULTS / "human_check_TO_FILL.csv", index=False)
        key.to_csv(RESULTS / "human_check_judge_key.csv", index=False)

    (RESULTS / "summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    main()
