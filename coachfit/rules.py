"""Deterministic fat-loss checks. No LLM anywhere in this file.

Every number the coach sees comes from here, so it can be unit-tested and
explained line by line. The LLM layer only turns this result into prose.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict

# Activity multipliers for TDEE (standard Mifflin-St Jeor companion factors).
ACTIVITY_FACTORS = {
    "sedentary": 1.2,
    "light": 1.375,
    "moderate": 1.55,
    "active": 1.725,
    "very_active": 1.9,
}

KCAL_PER_KG_FAT = 7700          # energy in 1 kg of body-fat loss
WEEKLY_LOSS_MIN = 0.005         # 0.5% of body weight per week
WEEKLY_LOSS_MAX = 0.010         # 1.0% of body weight per week
# Protein was removed from scope on 2026-09-28: the NHANES extract used for evaluation
# has no protein column, so a protein rule could not be validated on real data.
# Self-reported intake is commonly off by 10% or more. Instead of abstaining near a
# boundary (the evaluation showed ~half of real cases flip under this error), we show
# every label the client could have if the log is off by this much.
LOGGING_ERROR = 0.10
KCAL_FLOOR = {"male": 1500, "female": 1200}  # below this -> refer to a human

# Plausibility limits: outside these the input is probably a typo.
LIMITS = {
    "age": (18, 80),
    "height_cm": (130, 220),
    "weight_kg": (35, 250),
    "daily_kcal": (500, 7000),
}

DEFICIT_LABELS = ("no_deficit", "too_small", "appropriate", "too_large")


@dataclass
class ClientProfile:
    age: int
    sex: str                    # "male" | "female"
    height_cm: float
    weight_kg: float
    activity: str               # key of ACTIVITY_FACTORS
    daily_kcal: float


@dataclass
class Assessment:
    status: str                 # "ok" | "abstain"
    deficit_label: str | None = None
    confidence: str | None = None       # "high" | "low"
    possible_labels: list[str] | None = None  # labels reachable within +-LOGGING_ERROR
    bmr: float | None = None
    tdee: float | None = None
    bmi: float | None = None
    deficit: float | None = None
    target_deficit_range: tuple[float, float] | None = None
    target_intake_range: tuple[float, float] | None = None
    flags: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def validate(p: ClientProfile) -> list[str]:
    """Return a list of problems. Empty list means the profile is usable."""
    problems = []
    if p.sex not in KCAL_FLOOR:
        problems.append(f"sex must be 'male' or 'female', got {p.sex!r}")
    if p.activity not in ACTIVITY_FACTORS:
        problems.append(f"activity must be one of {list(ACTIVITY_FACTORS)}, got {p.activity!r}")
    for name, (lo, hi) in LIMITS.items():
        value = getattr(p, name)
        if value is None:
            problems.append(f"{name} is missing")
            continue
        if not lo <= value <= hi:
            problems.append(f"{name}={value} is outside the plausible range {lo}-{hi}")
    return problems


def bmr_mifflin(p: ClientProfile) -> float:
    base = 10 * p.weight_kg + 6.25 * p.height_cm - 5 * p.age
    return base + 5 if p.sex == "male" else base - 161


def _label(deficit: float, lo: float, hi: float) -> str:
    if deficit <= 0:
        return "no_deficit"
    if deficit < lo:
        return "too_small"
    if deficit <= hi:
        return "appropriate"
    return "too_large"


def assess(p: ClientProfile) -> Assessment:
    problems = validate(p)
    if problems:
        return Assessment(status="abstain", reasons=problems, flags=["invalid_input"])

    bmr = bmr_mifflin(p)
    tdee = bmr * ACTIVITY_FACTORS[p.activity]
    bmi = p.weight_kg / (p.height_cm / 100) ** 2
    deficit = tdee - p.daily_kcal

    lo = p.weight_kg * WEEKLY_LOSS_MIN * KCAL_PER_KG_FAT / 7
    hi = p.weight_kg * WEEKLY_LOSS_MAX * KCAL_PER_KG_FAT / 7

    label = _label(deficit, lo, hi)
    reachable = {_label(tdee - p.daily_kcal * f, lo, hi)
                 for f in (1 - LOGGING_ERROR, 1, 1 + LOGGING_ERROR)}
    # Labels are ordered, so everything between the extremes is reachable too.
    idx = [DEFICIT_LABELS.index(l) for l in reachable]
    possible = list(DEFICIT_LABELS[min(idx):max(idx) + 1])

    a = Assessment(
        status="ok",
        deficit_label=label,
        bmr=round(bmr, 1),
        tdee=round(tdee, 1),
        bmi=round(bmi, 1),
        deficit=round(deficit, 1),
        target_deficit_range=(round(lo, 1), round(hi, 1)),
        target_intake_range=(round(tdee - hi, 1), round(tdee - lo, 1)),
        possible_labels=possible,
    )

    # Confidence: shown to the coach as a range, not a reason to refuse.
    a.confidence = "low" if len(possible) > 1 else "high"
    if a.confidence == "low":
        a.flags.append("label_sensitive")
        a.reasons.append(
            f"if intake is logged {LOGGING_ERROR:.0%} off, the label could be "
            + " or ".join(possible))

    # Safety flags: these always go to a human, whatever the label says.
    if p.daily_kcal < KCAL_FLOOR[p.sex]:
        a.flags.append("below_kcal_floor")
        a.reasons.append(f"intake {p.daily_kcal:.0f} kcal is below the "
                         f"{KCAL_FLOOR[p.sex]} kcal floor for {p.sex} clients")
    if p.daily_kcal < bmr:
        a.flags.append("below_bmr")
        a.reasons.append(f"intake is below estimated BMR ({bmr:.0f} kcal); this is common in a "
                         "fat-loss deficit and is not a problem on its own while intake stays "
                         "above the safety floor")
    if bmi < 18.5:
        a.flags.append("underweight_bmi")
        a.reasons.append(f"BMI {bmi:.1f} is below 18.5; fat loss is not an appropriate goal")

    return a


def needs_human_review(a: Assessment) -> bool:
    return a.status == "abstain" or bool(
        {"below_kcal_floor", "underweight_bmi"} & set(a.flags))
