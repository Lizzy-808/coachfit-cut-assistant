import pytest

from coachfit.rules import ClientProfile, assess, bmr_mifflin, needs_human_review


def profile(**overrides):
    base = dict(age=30, sex="male", height_cm=175, weight_kg=80,
                activity="moderate", daily_kcal=2200, protein_g=150)
    base.update(overrides)
    return ClientProfile(**base)


def test_bmr_matches_hand_calculation():
    # 10*80 + 6.25*175 - 5*30 + 5 = 1748.75
    assert bmr_mifflin(profile()) == pytest.approx(1748.75)
    assert bmr_mifflin(profile(sex="female")) == pytest.approx(1582.75)


def test_appropriate_deficit():
    # TDEE = 1748.75*1.55 = 2710.6; target deficit 440-880; 2710.6-2200 = 510.6
    a = assess(profile())
    assert a.deficit_label == "appropriate"
    assert a.target_deficit_range == (440.0, 880.0)
    assert not needs_human_review(a)


@pytest.mark.parametrize("kcal,label", [
    (2800, "no_deficit"),
    (2400, "too_small"),
    (1700, "too_large"),
])
def test_other_labels(kcal, label):
    assert assess(profile(daily_kcal=kcal)).deficit_label == label


def test_logging_error_gives_label_range_not_review():
    # 2260 kcal: deficit 450.6, just inside appropriate (440). +-10% intake spans too_small..too_large.
    a = assess(profile(daily_kcal=2260))
    assert a.deficit_label == "appropriate"
    assert a.confidence == "low"
    assert a.possible_labels[0] == "too_small" and "appropriate" in a.possible_labels
    assert not needs_human_review(a)


def test_far_from_boundary_is_high_confidence():
    a = assess(profile(daily_kcal=3300))    # 590 kcal surplus; +-10% stays in surplus
    assert a.possible_labels == ["no_deficit"]
    assert a.confidence == "high"


def test_protein():
    assert assess(profile(protein_g=100)).protein_label == "insufficient"
    assert assess(profile(protein_g=None)).protein_label == "unknown"


def test_safety_flags():
    a = assess(profile(sex="female", weight_kg=60, height_cm=165, daily_kcal=1000))
    assert "below_kcal_floor" in a.flags
    assert needs_human_review(a)
    a = assess(profile(weight_kg=50, daily_kcal=1800))
    assert "underweight_bmi" in a.flags


def test_invalid_input_abstains():
    a = assess(profile(height_cm=17.5))
    assert a.status == "abstain"
    assert needs_human_review(a)
    assert assess(profile(activity="couch")).status == "abstain"
