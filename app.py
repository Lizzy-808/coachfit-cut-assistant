"""CoachFit Cut Assistant — Streamlit front end.

A coach enters one client profile; the page shows the rules' verdict (deficit label, confidence,
±10% label range), any safety warning, the numbers behind it, and the coach note from
`coachfit.explain` with a line saying whether the AI or the template wrote it.
The API key is read from `.streamlit/secrets.toml` and never typed into the page.

Run:  .venv/bin/streamlit run app.py
"""
import os

import streamlit as st

from coachfit.explain import explain, template_explanation
from coachfit.rules import ACTIVITY_FACTORS, ClientProfile, assess, needs_human_review

st.set_page_config(page_title="CoachFit Cut Assistant", page_icon="🏋️", layout="centered")

# Key from Streamlit secrets if present; never typed into the page.
try:
    if "OPENROUTER_API_KEY" in st.secrets:
        os.environ.setdefault("OPENROUTER_API_KEY", st.secrets["OPENROUTER_API_KEY"])
except Exception:
    pass

LABEL_STYLE = {
    "appropriate": ("✅", "success"),
    "too_small": ("⚠️", "warning"),
    "too_large": ("⚠️", "warning"),
    "no_deficit": ("⛔", "error"),
}

st.title("CoachFit Cut Assistant")
st.caption("Checks whether a client's daily calorie intake is a sensible fat-loss deficit. Rules do the maths; the AI only explains. "
           "Coach support only — not medical advice.")

with st.form("client"):
    c1, c2 = st.columns(2)
    age = c1.number_input("Age", 18, 80, 30)
    sex = c2.selectbox("Sex", ["male", "female"])
    height = c1.number_input("Height (cm)", 100.0, 230.0, 175.0, step=0.5)
    weight = c2.number_input("Weight (kg)", 30.0, 260.0, 80.0, step=0.5)
    activity = st.selectbox("Activity level", list(ACTIVITY_FACTORS),
                            index=2, format_func=lambda k: f"{k} (×{ACTIVITY_FACTORS[k]})")
    kcal = st.number_input("Average daily intake (kcal)", 0, 8000, 2200, step=50)
    use_llm = st.toggle("Use AI explanation", value=True,
                        help="Off = fixed template. Numbers are identical either way.")
    submitted = st.form_submit_button("Check client", type="primary")

if submitted:
    p = ClientProfile(age=age, sex=sex, height_cm=height, weight_kg=weight,
                      activity=activity, daily_kcal=kcal)
    a = assess(p)
    if use_llm:
        with st.spinner("Writing the coach note..."):
            note = explain(p, a)
    else:
        note = {**template_explanation(p, a), "source": "template", "note": "AI explanation off.",
                "tokens_in": 0, "tokens_out": 0, "cost_usd": 0.0}

    st.divider()
    if a.status == "abstain":
        st.error("**Cannot assess — check the profile.**\n\n" + "\n".join(f"- {r}" for r in a.reasons))
    else:
        icon, kind = LABEL_STYLE[a.deficit_label]
        getattr(st, kind)(f"{icon} **{a.deficit_label.replace('_', ' ').title()}** · "
                          f"confidence: {a.confidence}")
        if a.confidence == "low":
            st.info("📏 **Sensitive to logging error.** If intake is logged 10% off, the label could be: "
                    + " → ".join(l.replace("_", " ") for l in a.possible_labels)
                    + ". Check the food log before changing the plan.")
        if needs_human_review(a):
            st.warning("🧑‍⚕️ **Coach review needed before acting.**\n\n"
                       + "\n".join(f"- {r}" for r in a.reasons))

        m1, m2, m3 = st.columns(3)
        m1.metric("Maintenance (TDEE)", f"{a.tdee:.0f} kcal")
        m2.metric("Current deficit", f"{a.deficit:.0f} kcal")
        m3.metric("Target intake", f"{a.target_intake_range[0]:.0f}–{a.target_intake_range[1]:.0f}")
        m1.metric("BMR", f"{a.bmr:.0f} kcal")
        m2.metric("BMI", f"{a.bmi:.2f}")
        m3.metric("Possible labels (±10% log)", " / ".join(l.replace("_", " ") for l in a.possible_labels))

    st.subheader("Coach note")
    st.markdown(f"**{note['summary']}**\n\n{note['explanation']}\n\n**Next step:** {note['next_step']}")
    src = {"llm": "AI (gpt-4o-mini), numbers verified",
           "llm+guard": "AI (gpt-4o-mini), numbers verified; missing flags added by code",
           }.get(note["source"], "fixed template")
    st.caption(f"Written by: {src}. {note['note']} "
               f"Tokens {note['tokens_in']} in / {note['tokens_out']} out · ${note['cost_usd']:.5f}")

    with st.expander("Show the calculation"):
        st.json(a.to_dict())
