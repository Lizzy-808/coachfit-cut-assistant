"""Held-out check of v3: 20 NHANES cases never used in any earlier run or in tuning.

    .venv/bin/python -m eval.heldout_v3

Stratified so every flag type appears. Writes the notes the coach would see
(v3, after the coverage guard) to eval/results/heldout_v3.jsonl for hand grading.
"""
import json
import random
from pathlib import Path

import pandas as pd

from coachfit import explain as ex
from coachfit.rules import assess
from eval.run_eval import RESULTS, client, load_nhanes, nhanes_profile, pmap

SEED = 20261004
STRATA = [("below_kcal_floor", 4), ("underweight_bmi", 2), ("label_sensitive", 6),
          ("below_bmr", 4), ("none", 4)]


def used_ids() -> set[str]:
    used = set()
    for f in Path(RESULTS).rglob("nhanes_sample_ids.csv"):
        used |= {f"N{i}" for i in pd.read_csv(f).participant_id}
    for f in Path(RESULTS).rglob("flag_fidelity_cases.json"):
        used |= {c["case_id"] for c in json.loads(f.read_text())}
    return used


def main():
    df = load_nhanes()
    used = used_ids()
    pool = {}
    for r in df.itertuples():
        cid = f"N{r.participant_id}"
        a = assess(nhanes_profile(r))
        if cid in used or a.status != "ok":
            continue
        key = next((f for f, _ in STRATA[:-1] if f in a.flags), "none")
        pool.setdefault(key, []).append((cid, r))
    rng = random.Random(SEED)
    pick = [x for key, n in STRATA for x in rng.sample(pool[key], n)]
    rng.shuffle(pick)

    llm = client()

    def run(item):
        cid, r = item
        p = nhanes_profile(r)
        a = assess(p)
        out = ex.explain(p, a, client=llm, prompt="v3")
        return {"case_id": cid, "flags": a.flags, "label": a.deficit_label,
                "possible_labels": a.possible_labels, "source": out["source"],
                "missing_flags_raw": out["missing_flags_raw"], "llm_output": out["llm_output"],
                "shown": {k: out[k] for k in ("summary", "explanation", "next_step")},
                "cost_usd": out["cost_usd"]}

    recs = pmap(run, pick)
    (RESULTS / "heldout_v3.jsonl").write_text("\n".join(json.dumps(r) for r in recs))
    print(f"{len(recs)} cases, overlap with earlier runs: {len({r['case_id'] for r in recs} & used)}")
    print("guard added flags on", sum(r["source"] == "llm+guard" for r in recs), "notes")


if __name__ == "__main__":
    main()
