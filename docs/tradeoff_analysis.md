# CoachFit Cut Assistant — Business & Technical Trade-off Analysis

LIU ZEYUAN · PE6201 Section B · End-of-Course Project

## 1. The decision

A gym coach needs to know, per client, whether daily intake is a sensible fat-loss deficit. In my system **deterministic rules make every decision and a rented language model only explains it**: rules compute BMR, TDEE, the deficit label, protein status and safety flags; `gpt-4o-mini` turns the result into a short note; my guard rejects any note containing a number the rules did not produce, and a fixed template replaces it. Below I argue for that split, price it, and report what the evaluation forced me to change.

## 2. Alternatives compared

| Option | Label accuracy | Cost per check | Main failure mode |
|---|---|---|---|
| LLM classifies directly (formula in prompt) | 38% (19% within 100 kcal of a boundary) | ~US$0.00004 | Confident arithmetic errors |
| TF-IDF classifier on note text (A1) | 39.6% | ~0 | Learns wording, not energy balance |
| Rules + fixed template | 100%* | 0 | Stiff wording, no tailoring |
| **Rules + LLM note + guard (chosen)** | 100%* | US$0.00014, ~2 s | Fluent note that misstates a relation |
| RAG or agent | — | higher | No documents to retrieve, no multi-step task |

\*Against labels computed independently in Excel on 787 valid NHANES rows; 13 rows with impossible intake (e.g. 45 kcal/day) were refused rather than guessed. Majority baseline: 25%.

The first two rows decide it. Even with the formula in the prompt, the model got barely one case in three right, and one in five near a boundary — exactly where a coach needs help. This is an arithmetic task dressed as a language task, so the model belongs downstream of the decision.

The honest counterpoint is row three: the template is correct by construction and free, so the LLM adds readability, not correctness. I kept it because a note written for this client should read faster than a fixed paragraph, and the guard and fallback cap its downside. I have not measured that gain with coaches; it is the first thing I would test.

## 3. Build vs buy, layer by layer

- **Decision logic — own.** It is the only part specific to this problem, and it must be checkable line by line: 21 unit tests against hand calculations.
- **Model — rent.** `openai/gpt-4o-mini` via OpenRouter. Rephrasing given facts is commodity work; a small model suffices, and swapping is one line.
- **Interface and orchestration — own code on Streamlit.** One call per check needs no framework.
- **Evaluation — own harness, rented judge.** `deepseek/deepseek-chat` judges, deliberately from a different vendor than the model it grades.

**Cost to serve.** US$0.00014 and ~2 seconds per note: about US$0.01 a month for a coach checking 20 clients weekly, US$11 a month for 1,000 coaches. Cost is not the constraint; trust is. Low-code was not tried: arithmetic that must be unit-tested does not fit a no-code builder. Three full evaluation runs cost US$0.20.

## 4. What the evaluation changed

**Run 1 found my own bug.** The guard rejected 42 of 226 notes for "invented numbers"; every one was a false positive — the model wrote "a deficit of −90 kcal" and my regex read 90. The judge, the same `gpt-4o-mini`, also failed correct "eat less" advice. Run 1's 19% and 36% judge scores measured my tooling, not the model.

**Run 2 fixed the guard and changed the judge.** I switched to a judge from another vendor, then hand-graded 20 of its verdicts. Against my labels it agreed 75% of the time, with FAIL precision 60% and recall 86%: it catches most real errors but raises many false alarms, mostly on correct v2 notes. Its scores are therefore a lower bound. It was also unstable: in 10 v1 cases both runs' notes wrote a surplus as a negative deficit — which its rubric explicitly accepts — and it passed them in run 2 but failed them in run 3, pulling v1 from 94% to 81%. Hand grading, not the judge, is my headline metric.

Hand grading exposed a design flaw rather than a model flaw. Five of my seven hand-graded failures were one pattern: the rules labelled a client *appropriate* but also flagged "intake below BMR", and the model resolved the contradiction by telling the client to eat more. I reworded the flag to state that eating below BMR is normal in a deficit while intake stays above the safety floor. The deterministic count of that error fell from 4/10 to 0/10.

**Prompt v1 → v2 was a single change:** the rules pre-write every comparison ("150 g is within the 128–176 g target") so the model never compares numbers itself. v1 had written "150 g is *above* 128–176 g" — every number true, the relation false, and invisible to the number guard. Judge pass rate rose from 81% to 89% in the final run. **Hand-graded on a random sample of 30 final notes: [X/30 = Y%] had no factual or direction error, against a target of 95%.**

**Abstention became a range.** I first flagged cases within 50 kcal of a label boundary for review. Testing that against a ±10% logging error — typical for self-reported intake — showed it caught only 28% of the cases whose label would flip, while 48% of all real cases were sensitive. Catching 76% would have sent 38% of clients to review, which a coach would soon ignore. I replaced it: the tool shows every label reachable within ±10% ("too small → appropriate") and reserves forced review for real safety cases — intake below 1,200/1,500 kcal or BMI below 18.5 — all 27 of which were routed correctly.

## 5. Risks and limitations

- **The labels are finer than the data.** A 10% logging error is about as wide as the whole "appropriate" band, so half of real verdicts are uncertain. The range makes that visible; it does not remove it.
- **Evaluation is thin.** Twenty hand labels measure the judge; thirty measure the headline metric. Both come from me, the system's author. A held-out set graded by a coach such as Coach Huang is the missing check.
- **Data provenance.** I did not record the NHANES cycle or intake variable in A1; NHANES has no protein, so protein logic is tested only on handwritten cases.
- **No real users.** Readability and time saved — the actual business value — are untested.
- **Responsible use.** Healthy adults only; no medical advice; under-18s refused; no identifiers sent to the model (PDPA). Safety cases keep a human in the loop (IMDA Model AI Governance Framework); the number guard targets OWASP LLM09, misinformation.

## 6. When the answer changes

If coaches entered free-text food logs, the model would move into the decision path — extracting calories — and would need its own accuracy evaluation. If a coach test showed its notes read no faster than the template, I would drop it: the rules already carry all of the correctness.

---
*Tools: Claude (Anthropic) helped write code and draft this text; ChatGPT translated evaluation material for reading. All figures come from `eval/results/`.*
