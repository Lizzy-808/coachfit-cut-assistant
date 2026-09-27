"""How far can the model judge be trusted? Compares it with a person's verdicts.

1. Open eval/results/human_check_TO_FILL.csv and fill `your_verdict (PASS/FAIL)` for every row,
   WITHOUT looking at eval/results/human_check_judge_key.csv.
2. .venv/bin/python -m eval.judge_agreement

FAIL is the positive class: we want the judge to catch bad notes.
"""
from pathlib import Path

import pandas as pd

RESULTS = Path(__file__).resolve().parent / "results"


def main():
    human = pd.read_csv(RESULTS / "human_check_TO_FILL.csv")
    key = pd.read_csv(RESULTS / "human_check_judge_key.csv")
    col = "your_verdict (PASS/FAIL)"
    human[col] = human[col].astype(str).str.strip().str.upper()
    missing = human[~human[col].isin(["PASS", "FAIL"])]
    if len(missing):
        raise SystemExit(f"Fill PASS or FAIL for items: {missing.item.tolist()}")

    d = human.merge(key, on="item").rename(columns={col: "human"})
    col = "human"
    tp = int(((d.judge == "FAIL") & (d[col] == "FAIL")).sum())
    fp = int(((d.judge == "FAIL") & (d[col] == "PASS")).sum())
    fn = int(((d.judge == "PASS") & (d[col] == "FAIL")).sum())
    tn = int(((d.judge == "PASS") & (d[col] == "PASS")).sum())
    print(f"items: {len(d)}   agreement: {(tp + tn) / len(d):.0%}")
    print(f"judge FAIL precision: {tp / max(tp + fp, 1):.0%}  (of notes the judge failed, how many were really bad)")
    print(f"judge FAIL recall:    {tp / max(tp + fn, 1):.0%}  (of really bad notes, how many the judge caught)")
    print(f"confusion: TP={tp} FP={fp} FN={fn} TN={tn}")
    print("\nDisagreements:")
    for r in d[d.judge != d[col]].itertuples():
        print(f"  item {r.item} ({r.case_id}, {r.prompt}): judge {r.judge} / you {r.human}"
              f"  - judge said: {r.judge_reason}")
    out = d[["item", "case_id", "prompt", col, "judge"]]
    out.to_csv(RESULTS / "judge_agreement.csv", index=False)


if __name__ == "__main__":
    main()
