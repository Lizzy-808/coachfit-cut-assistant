# CoachFit Cut Assistant — Business & Technical Trade-off Analysis

LIU ZEYUAN · PE6201 Section B · End-of-Course Project

## 1. The decision

A gym coach needs to know, per client, whether daily intake is a sensible fat-loss deficit. In my system **deterministic rules make every decision and a rented language model only explains it**: rules compute BMR, TDEE, the deficit label and safety flags; `gpt-4o-mini` writes a short note for the coach; two guards I wrote then check it — any number the rules did not produce sends the note back to a fixed template, and any flag the note leaves out is appended by code. Out of scope: food logs, macronutrient targets, and protein (section 4 explains why).

## 2. Alternatives compared

| Option | Correct verdict | US$ per successful check | Main failure mode |
|---|---|---|---|
| Coach by hand | — | 4.89 | 5–10 minutes; coaches round differently |
| LLM classifies directly (formula in prompt) | 37–40% | ~3.00† | Silent arithmetic errors |
| Rules + fixed template | 100%* | 1.08 | Stiff wording |
| **Rules + LLM note + guards (chosen)** | 100%* | 1.08–1.77‡ | Fluent note that misstates a relation |

\*Against labels computed independently in Excel on 787 valid NHANES rows — this checks my arithmetic, not the model; the model is measured in section 4. Majority baseline 25%. †Assumes errors are caught; they are silent, so the true cost is higher. ‡At the measured 20/20 and at its 95% lower bound, 86%.

Given the formula, the LLM got barely one case in three right across four runs, and about one in five within 100 kcal of a boundary — where a coach most needs help. This is an arithmetic task dressed as a language task, so the model belongs downstream of the decision. The honest counterpoint is row three: the template is correct by construction and free, so the LLM can only add readability. Section 3 prices how much it must add.

## 3. Is it worth building? (Class 5)

**Cost per successful check** = variable cost + (1 − success rate) × cost of a failure. A failure is a note the coach must redo by hand: 7.5 minutes at S$50 an hour (one PT session at my gym), US$4.89 at 0.7823 USD/SGD on 28 September. Tokens cost US$0.00014 per note — irrelevant. What dominates is the 22% of real checks the rules deliberately send to the coach (mostly intake below the safety floor) and the note's error rate. At v2's measured 50% the LLM note had to save a coach **225 seconds** per check to beat the template; at v3's 20/20 it breaks even at zero, and at the 86% lower bound it must save **63 seconds**. That is my kill condition, written before any coach trial: if notes do not read that much faster than the template, drop the LLM — the rules carry all the correctness.

**What it buys.** Scale only: the same check, cheaper, per client — an efficiency case, defended as one. It fails the free-label test: whether a deficit estimate was right would show in weigh-ins, but those are self-reported and never flow back automatically. Scope is weak; the rules could serve a dietitian-referral screen, but nobody has asked for it.

**Data readiness.** NHANES passes accessibility and standardisation, but real gym data fails *quality* and *consistency*: one-day recalls under-report so often that 18.5% of NHANES adults fall below the 1,200/1,500 kcal floor, and client logs vary by app. The operating model — who records intake, weekly, with PDPA consent — is the bottleneck, not the model.

## 4. What the evaluation changed

**Headline metric (instructor's suggestion):** does the note state every flag the rules raised and invent none, scored 0/1 by hand?

- **v2: 10/20.** No note invented a flag; all ten failures were omissions. Six omitted "protein not logged" — my NHANES extract has no protein column, lost when I prepared it in A1, so a protein rule could never be validated on real data. I removed protein from scope rather than ship an untested rule. Of the other four, three omitted the logging-error warning and one the verdict itself.
- **v3 added one step:** code checks each flag and appends any the note left out. On **20 new held-out cases** never used before, I scored **20/20**. By the automatic check, the model alone covered 8/20 and the guard supplied the rest — the same principle as the arithmetic: what must be right is enforced by code, not requested of the model. My review also caught a display bug ("BMI 18.5 is below 18.5" for a client at 18.46), since fixed.

**Earlier runs shaped the design.** Run 1's guard rejected 42 of 226 notes for "invented numbers" — all false positives: the model wrote "−90 kcal" and my regex read 90. Its judge, the same `gpt-4o-mini`, also failed correct advice, so I switched to `deepseek-chat` and measured it against my 20 hand labels: 75% agreement, FAIL precision 60%, recall 86%, and unstable between runs. Judge scores are a lower bound, not the metric. Hand grading showed the rules themselves confused the model: flagging "below BMR" beside an *appropriate* label made it say "eat more"; rewording the flag cut that from 4/10 to 0/10. Prompt v2 pre-wrote every comparison after v1 wrote "150 g is *above* 128–176 g"; it raised judged correctness (87% → 97%) but lowered flag coverage (80% → 54%) — the trade-off v3's guard removes.

**Abstention became a range.** Flagging cases within 50 kcal of a boundary caught only 28% of those a ±10% logging error would flip; 48% of real cases are that sensitive, and catching 76% would have sent 38% of clients to review. The tool now shows every label reachable within ±10% and forces review only for safety cases — all 27 routed correctly.

## 5. Build vs buy

Own the decision logic (24 unit tests), the guards, the evaluation set and harness. Rent the model (`gpt-4o-mini` via OpenRouter, swappable in one line), the judge and Streamlit. A competitor could rent all of that by next Tuesday; what they could not copy quickly is consented client data inside a gym's weekly workflow, which this project does not yet have. Low-code was not tried: unit-tested arithmetic does not fit a no-code builder. All evaluation cost US$0.30.

## 6. Limitations and when the answer changes

The four labels are finer than the data: a 10% logging error is as wide as the "appropriate" band. My hand grades cover 60 notes, all graded by me, the system's author; a coach-graded set is the missing check. No real coach has used the tool, so the time saving — the whole business case — is unmeasured. Responsible use: healthy adults only, under-18s refused, no identifiers sent to the model, human review for safety cases (IMDA framework), guards against misinformation (OWASP LLM09). If coaches entered free-text food logs, the model would move into the decision path and need its own accuracy evaluation.

---
*Tools: Claude (Anthropic) helped write code and draft this text; ChatGPT translated evaluation material for reading. All figures come from `eval/results/`.*
