"""Cost per SUCCESSFUL check — the Class 5 C2 method applied to CoachFit.

    .venv/bin/python -m eval.cost_to_serve [--success 0.90]

cost per successful task = variable cost + (1 - success rate) x cost of one failure
(Class 5 C2, `cost_per_successful_task`). Every figure is US dollars. Never read the
point estimate alone: the break-even and sensitivity table are printed beside it.

A "failure" is a note that misses or invents a flag. The coach has to redo the
check by hand, so a failure costs one manual check. Designed escalations (safety
cases) also cost one manual check each, whatever the note says.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from coachfit.rules import assess, needs_human_review

RESULTS = Path(__file__).resolve().parent / "results"

# ── CONFIG · checked 2026-09-28 ─────────────────────────────────────────────────────
SGD_TO_USD = 0.7823                    # open.er-api.com and frankfurter.app, 28 Sep 2026
COACH_SGD_PER_HOUR = 50.0              # one PT session at the author's gym (Coach Huang), ~1 hour
MANUAL_MINUTES = (5.0, 10.0)           # author's estimate for one check by hand
CHECKS_PER_MONTH = 20 * 52 / 12        # one coach, 20 clients, weekly check

# Measured in eval/results/summary.json (run 3), per check.
VAR = {
    "llm_only": 0.00004,               # part B: 100 checks cost US$0.00395
    "rules_template": 0.0,
    "rules_llm": 0.000145,             # part D, v2
}
LLM_ONLY_SUCCESS = 0.38                # part B label accuracy; the note itself is not even checked
TEMPLATE_SUCCESS = 1.0                 # template states every flag by construction (unit-tested)
# ────────────────────────────────────────────────────────────────────────────────────


def cost_per_successful_task(var_usd, success_rate, failure_usd):
    """Class 5 C2, verbatim formula."""
    return var_usd + (1.0 - success_rate) * failure_usd


def escalation_rate() -> float:
    """Share of real NHANES checks the rules send to the coach (safety or invalid input)."""
    from eval.run_eval import load_nhanes, nhanes_profile
    df = load_nhanes()
    return sum(needs_human_review(assess(nhanes_profile(r))) for r in df.itertuples()) / len(df)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--success", type=float, default=None,
                    help="hand-graded flag-fidelity rate of the LLM notes (0-1)")
    args = ap.parse_args()

    usd_per_min = COACH_SGD_PER_HOUR * SGD_TO_USD / 60
    manual = [m * usd_per_min for m in MANUAL_MINUTES]
    manual_mid = sum(manual) / 2
    esc = escalation_rate()

    print(f"coach time US${usd_per_min * 60:.2f}/h · one manual check US${manual[0]:.2f}–{manual[1]:.2f}"
          f" (mid US${manual_mid:.2f})")
    print(f"designed escalations (safety or invalid input): {esc:.1%} of real checks\n")

    rows = {"manual (coach by hand)": manual_mid,
            "LLM classifies directly": cost_per_successful_task(VAR["llm_only"], LLM_ONLY_SUCCESS, manual_mid),
            "rules + template": cost_per_successful_task(VAR["rules_template"], TEMPLATE_SUCCESS, manual_mid)
                                + esc * manual_mid}
    if args.success is not None:
        rows["rules + LLM note (chosen)"] = (cost_per_successful_task(VAR["rules_llm"], args.success, manual_mid)
                                             + esc * manual_mid)

    print(f"{'option':<28}{'US$/successful check':>22}{'US$/coach/month':>18}")
    for k, v in rows.items():
        print(f"{k:<28}{v:>22.3f}{v * CHECKS_PER_MONTH:>18.2f}")

    # What the LLM note must buy to beat the template: coach reading time saved per check.
    print("\nLLM note vs template — the note must save the coach this much reading time per check:")
    print(f"{'flag fidelity':>14}{'extra US$/check':>17}{'break-even seconds saved':>26}")
    centre = args.success if args.success is not None else 0.90
    for p in sorted({0.80, 0.85, 0.90, 0.95, 0.99, 1.0, round(centre, 2)}):
        extra = cost_per_successful_task(VAR["rules_llm"], p, manual_mid) - 0.0
        mark = "  ← measured" if args.success is not None and abs(p - args.success) < 1e-9 else ""
        print(f"{p:>14.0%}{extra:>17.3f}{extra / usd_per_min * 60:>26.0f}{mark}")

    out = {"sgd_to_usd": SGD_TO_USD, "coach_usd_per_hour": round(usd_per_min * 60, 2),
           "manual_check_usd": [round(m, 2) for m in manual], "escalation_rate": round(esc, 4),
           "checks_per_month": round(CHECKS_PER_MONTH, 1), "success_rate_llm_note": args.success,
           "usd_per_successful_check": {k: round(v, 4) for k, v in rows.items()}}
    (RESULTS / "cost_to_serve.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
