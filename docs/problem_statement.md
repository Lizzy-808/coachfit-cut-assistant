# Project Problem Statement — revised for final submission

Name: LIU ZEYUAN · Section: B · Original submitted 21 Aug 2026 · Revised 29 Sep 2026

## 1 · Working title

**CoachFit Cut Assistant — checks a client's fat-loss intake for gym coaches.**

## 2 · The problem, and why it matters

A personal trainer cannot quickly tell whether a fat-loss client's daily intake is a sensible deficit: the answer depends on a per-client energy calculation, not the calorie number alone. By hand it takes 5–10 minutes per client — about 2 to 3 hours a week for a coach with 20 clients — and coaches round differently, so similar clients get different advice. A general chatbot is not the answer: in my tests gpt-4o-mini labelled these cases correctly only 37–40% of the time even when given the formula (majority baseline 25%). Calorie apps such as MyFitnessPal and MacroFactor set targets for one self-tracking user; they do not give a coach a consistent check across clients, show how sensitive the verdict is to logging error, or send unsafe cases to a person. **Out of scope:** meal plans, protein and other macronutrient targets, free-text food logs, under-18s, and any medical condition.

## 3 · Who it's for, and the domain

Primary user: a personal trainer in a commercial gym. Persona: *Coach Huang, a personal trainer at my gym whom I consulted while scoping this project, checks each fat-loss client's weekly average intake between sessions; he knows what maintenance calories are but does not work out TDEE per client, and has never seen a confidence range.* With the tool he gets a verdict, the numbers behind it and a next step in seconds, and knows which clients need his own attention. Domain: fitness coaching and nutrition planning.

## 4 · Why AI — and which kind?

The decision is arithmetic, so **rules make it**: BMR (Mifflin-St Jeor) × activity factor = TDEE; target deficit = 0.5–1% of body weight per week; label = no_deficit / too_small / appropriate / too_large. The non-AI baseline wins outright — rules 100% against reference labels, a foundation model classifying directly 37–40%. A foundation model is used only where it adds value: turning the rule output into a plain-English note for the coach. It is kept out of the arithmetic and out of safety decisions. No RAG (no documents to ground on) and no agent (no multi-step task).

## 5 · Proposed approach — build vs buy

| Layer | Own / rent | What, and why |
|---|---|---|
| Interface | Own, on Streamlit | Fastest route to something a coach can use |
| Decision logic | **Own** | Rules, safety flags, logging-error range — the problem-specific part, unit-tested |
| Model | Rent | `openai/gpt-4o-mini` via OpenRouter, explanation only. My guards check every note: a number not from the rules sends it back to a fixed template; a flag it left out is appended by code |
| Evaluation | Own, rented judge | My harness; `deepseek/deepseek-chat` judges, a different vendor from the model it grades |

**Cost (Class 5 method):** tokens are US$0.00014 per note, but a note the coach must redo costs a manual check — US$4.89 of coach time — so cost per *successful* check is set by the error rate and by the 22% of real cases routed to the coach, not by the model price. The rules path is free and works when the API is down. **Low-code:** not tried — the core is arithmetic that must be unit-tested, which no-code builders do not support, so I went straight to code.

## 6 · Data

- **NHANES** (CDC, public domain): 800 adults aged 20–35 — age, sex, height, weight, activity level, daily kcal — prepared in A1. Reference labels were computed in Excel, independently of this code. *Limitations: I did not record the survey cycle or intake variable in A1, and the extract lost the protein column — so protein could not be validated on real data and is out of scope.*
- **14 handwritten cases** (safety, borderline, invalid, typical), expected outcomes fixed in a CSV before any run.
- **25 fresh NHANES cases** for a pre-registered confirmatory test, never used in any earlier run or in tuning.
- **Leakage:** inputs hold raw measurements only; BMR, TDEE and deficit never appear in the input.
- **Privacy:** no identifiers are sent to the model; real client data would need consent and a purpose notice under Singapore's PDPA.

## 7 · Success metric & how I evaluate it

**Metric: flag fidelity** — for 20 cases covering every flag type, does the coach note state every flag the rules raised and invent none? Scored 0/1 by hand. Target ≥ 19/20. **Result, from a pre-registered, paired, blind test on 25 new cases: the model's own notes passed 10/25; with v3's code appending any omitted flag, 25/25 (95% CI 86–100%). The detector caught all 16 omissions and the guard added no errors.** This measures what the model does; the rules themselves are checked separately against independently computed reference labels (787/787), which tests my arithmetic, not the model. Baseline: a chatbot answering directly gets even the label right only 37–40% of the time. I also report the model judge's precision and recall against my hand labels (75% agreement, FAIL precision 60%, recall 86%) and how often the system refuses or routes to a human. All evaluation cost US$0.31.

## 8 · Risks, limitations & responsible use

| Risk | Mitigation (built) |
|---|---|
| **Silent failure:** a fluent note that misstates a relation or quietly leaves out a flag (unguarded, 15 of 25 notes did) | Comparisons pre-computed by code; number guard; flag-coverage guard; pre-registered hand audit |
| Dangerously low intake labelled "appropriate" | Safety floor (1,200 kcal women / 1,500 men) and BMI < 18.5 force coach review |
| Bad input, confident answer | Plausibility limits: the tool refuses and says why (13 of 800 NHANES rows) |
| Food logs 10%+ inaccurate | Shows every label reachable within ±10% instead of one confident answer |
| Model outage or cost spike | Template fallback, identical numbers |

Intended use: coach support for healthy adults. Non-use: medical advice, eating disorders, pregnancy, under-18s. Frameworks: IMDA Model AI Governance Framework (human in the loop for safety cases); OWASP Top 10 for LLM Applications 2025 — LLM09 Misinformation, LLM02 Sensitive Information Disclosure; EU AI Act — not high-risk, every note labelled as AI- or template-written.

## 9 · Smallest first version

One client profile → rules → one gpt-4o-mini call → one coach note. **It worked when** a 30-year-old, 80 kg man on 2,200 kcal returned *appropriate*, a 511 kcal deficit, and a note whose every number matched the rules. Everything since extends this path.

---
*Tools: Claude (Anthropic) helped draft code and text; ChatGPT translated evaluation material for reading. Figures come from runs in `eval/results/`.*
