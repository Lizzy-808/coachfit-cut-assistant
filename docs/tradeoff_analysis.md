# CoachFit Cut Assistant — Business & Technical Trade-off Analysis

LIU ZEYUAN · PE6201 Section B · End-of-Course Project

## 1. The decision

A gym coach needs to know, per client, whether daily intake is a sensible fat-loss deficit. In my system **deterministic rules make every decision and a rented language model only explains it**: rules compute BMR, TDEE, the deficit label, protein status and safety flags; `gpt-4o-mini` writes a short note for the coach; my guard rejects any note containing a number the rules did not produce, and a fixed template replaces it. Food logs and carbohydrate/fat targets are out of scope: the input is a structured profile and an average daily intake.

## 2. Alternatives compared

| Option | Correct verdict | US$ per successful check | Main failure mode |
|---|---|---|---|
| Coach by hand | — | 4.89 | 5–10 minutes; coaches round differently |
| LLM classifies directly (formula in prompt) | 38% | 3.03† | Silent arithmetic errors |
| Rules + fixed template | 100%* | 1.08 | Stiff wording |
| **Rules + LLM note + guard (chosen)** | 100%* | [C] | Fluent note that misses or invents a flag |

\*Against labels computed independently in Excel on 787 valid NHANES rows. This checks my arithmetic, not the model; the model is measured in section 4. Majority baseline: 25%. †Assumes every error is caught; these errors are silent, so the true cost is higher.

The LLM, given the formula, got one case in three right and one in five within 100 kcal of a boundary — where a coach most needs help. This is an arithmetic task dressed as a language task, so the model belongs downstream of the decision. The honest counterpoint is row three: the template is correct by construction and free, so the LLM can only add readability, and section 3 prices exactly how much readability it must buy.

## 3. Is it worth building? (Class 5)

**Cost per successful check** = variable cost + (1 − success rate) × cost of a failure. A failure is a note the coach must redo by hand: 7.5 minutes at S$50 an hour (one PT session at my gym), US$4.89 at 0.7823 USD/SGD on 28 September. Tokens cost US$0.00014 per note — irrelevant. Two terms dominate: the 22% of real checks the rules deliberately send to the coach (mostly intake below the safety floor), and the LLM's error rate. At my measured flag fidelity of [F], the LLM note costs [E] more per check than the template, so **it pays only if it saves the coach at least [S] seconds of reading per check**. That is my kill condition, written before any coach trial: if notes do not beat the template by that margin, drop the LLM — the rules carry all the correctness.

**What it buys.** Scale only: the same check, cheaper, per client — an efficiency case, defended as one. It fails the free-label test: whether a deficit estimate was right would show in weigh-ins, but those are self-reported and never flow back automatically. Scope is weak; the rules could serve a dietitian-referral screen, but nobody has asked for it.

**Data readiness.** NHANES passes the accessibility and standardisation tests, but real gym data fails *quality* and *consistency*: one-day intake recalls under-report so often that 18.5% of NHANES adults fall below the 1,200/1,500 kcal floor, and client logs vary by app. The operating model — who records intake, weekly, with consent under PDPA — is the real bottleneck, not the model.

## 4. What the evaluation changed

**Headline metric (instructor's suggestion):** for 20 cases covering every flag type, did the note state every flag the rules raised and invent none, scored 0/1 by hand? **[X/20].**

**Run 1 found my own bug.** The guard rejected 42 of 226 notes as "invented numbers"; all were false positives — the model wrote "a deficit of −90 kcal" and my regex read 90. The judge, the same `gpt-4o-mini`, also failed correct "eat less" advice. Run 1 measured my tooling, not the model.

**Run 2 fixed both.** A judge from another vendor (`deepseek-chat`) agreed with my 20 hand labels 75% of the time: FAIL precision 60%, recall 86%. It over-flags, and it drifted between runs, failing ten negative-deficit notes its own rubric accepts. Judge scores are a lower bound, not the metric.

**Hand grading exposed a design flaw.** Five of my seven failures shared one cause: the rules flagged "below BMR" beside a label that did not call for eating more (usually *appropriate*), and the model resolved the contradiction by saying "eat more". I reworded the flag; that error fell from 4/10 to 0/10.

**Prompt v2 made one change:** the rules pre-write every comparison ("150 g is within 128–176 g"), because v1 wrote "150 g is *above* 128–176 g" — true numbers, false relation, invisible to the number guard. Judge pass rate rose from 81% to 89%.

**Abstention became a range.** Flagging cases within 50 kcal of a boundary caught only 28% of those a ±10% logging error would flip, while 48% of real cases are that sensitive; catching 76% would have sent 38% of clients to review. The tool now shows every label reachable within ±10% and reserves forced review for safety cases — all 27 routed correctly.

## 5. Build vs buy

Own the decision logic (the problem-specific part, 21 unit tests), the evaluation set and harness. Rent the model (`gpt-4o-mini` via OpenRouter, swappable in one line), the judge, and Streamlit. A competitor could rent all of that by next Tuesday; what they could not copy quickly is consented client data inside a gym's weekly workflow — which this project does not yet have. Low-code was not tried: unit-tested arithmetic does not fit a no-code builder. Three evaluation runs cost US$0.20.

## 6. Limitations and when the answer changes

The four labels are finer than the data: a 10% logging error is as wide as the "appropriate" band. My evaluation is small and graded by the system's author; a coach-graded hold-out set is the missing check. I did not record the NHANES cycle in A1, and protein is tested only on handwritten cases. No real coach has used it, so the time saving — the whole business case — is unmeasured. Responsible use: healthy adults only, under-18s refused, no identifiers sent to the model, human review for safety cases (IMDA framework), number guard against misinformation (OWASP LLM09). If coaches entered free-text food logs, the model would move into the decision path and need its own accuracy evaluation.

---
*Tools: Claude (Anthropic) helped write code and draft this text; ChatGPT translated evaluation material for reading. All figures come from `eval/results/`.*
