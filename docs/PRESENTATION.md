# Druggie: pitch and demo guide

For the HackHarvard 2026 judging, Regeneron "Reinvent Clinical Trials" (Sus or Not).
Aim for **3 minutes of pitch and demo**, then Q&A. Times are cumulative.

---

## The one sentence

> Druggie turns a drug-safety reviewer's slowest, least consistent task, deciding whether a drug caused an adverse event, into a deck of cards that are already sorted, scored and backed by evidence. The doctor still makes every call.

Say this early and say it again at the end.

---

## Slide outline (6 slides + live demo)

| # | Slide | Visual | Time |
|---|---|---|---|
| 1 | **The clock.** A serious, unexpected, possibly drug-related event goes to the FDA in 15 days, or 7 if it's fatal. | One big "15 days / 7 days" (21 CFR 312.32) | 0:00–0:20 |
| 2 | **Why it's slow and inconsistent.** It's done by hand, the evidence sits in 3+ systems, and reviewers disagree (Naranjo vs. WHO-UMC κ = 0.14). Naranjo takes about 10 minutes per case. | Three short bullets | 0:20–0:45 |
| 3 | **Druggie in one picture.** | `docs/images/diagram-flow.png` | 0:45–1:00 |
| 4 | **Live demo** (see the script below) | The app | 1:00–2:15 |
| 5 | **How it's built.** Two engines: Naranjo per case, population signals across all patients. | `diagram-engine.png`, then `diagram-architecture.png` if time allows | 2:15–2:40 |
| 6 | **Honest limits and what's next.** | The "Limits" section of the README | 2:40–3:00 |

---

## Pitch script

**[Slide 1: the clock]**
"When a patient in a clinical trial has a serious adverse event, a safety physician has one question to answer: *did our drug cause this?* If the answer might be yes, the FDA needs a report within 15 days, or 7 if the patient died or nearly did."

**[Slide 2: the pain]**
"Today that answer is put together by hand. The physician rebuilds the timeline from one system, opens every FDA label, digs up the labs and scores it from memory. It takes about ten minutes per case before any writing starts. Two standard methods for the same cases agree only slightly better than chance, with a kappa of 0.14."

**[Slide 3: the flow]**
"Druggie does the gathering and sorting so the physician can spend their time on judgement. Cases come in sorted by priority and grouped by the drug most likely to be responsible. Each case is a card: the patient on the front, the evidence on the back. One swipe records the decision."

**[Demo: see below]**

**[Slide 5: how]**
"Two engines run ahead of time. The first scores every drug a patient was on against the Naranjo questions the data can answer. That's six of the ten: label, timing, stopping, restarting, prior reactions and labs. Every answer has a written reason. The second looks across the whole population. It uses PCA and k-means for groups of similar patients, and the PRR test that regulators use for drug→condition signals. Together they set a 0–100 priority."

**[Slide 6: limits and next]**
"We're upfront about the limits. The patients are synthetic, so we planted real reactions for the tool to find. Patterns are not proof. Four Naranjo questions need a clinician, so we leave them to the clinician. Next we'd connect real trial data with dates, starting with the Supabase loader we've already built."

**[Close]**
"Druggie never files a report and never makes the call. It makes sure that when the physician makes it, they're looking at the right case with all the evidence in front of them."

---

## Live demo script (about 75 seconds)

Start the app before you go on stage: `cd frontend && npm run dev`. Also run `python server.py` if you'll show the AI draft. **Open the app in a fresh/incognito window** so decisions saved in the browser from rehearsals don't hide cards.

1. **Insights → "Swipe these first"** (10s)
   "Before anyone reads a case, Druggie ranks them. The top case scores 82. Across 184 patients, 5 of 10 people on epoetin alfa developed stage 4 kidney disease, 29 times the rate in everyone else."
2. **Review → Amiodarone deck** (10s)
   "Cases are grouped by the drug most likely to have caused them. This one's a liver injury."
   Front of the card: *Numbers Moen, 59, hepatic enzyme increased, 12 Apr 2022, right-side pain, nausea, fatigue.*
3. **Press Space to flip → Drug tab** (10s)
   "Amiodarone's FDA label, already pulled, with the boxed warning on top."
4. **Reasons tab** (25s). **This is the money shot. Slow down.**
   "Each Naranjo question has an answer and a reason. It's in the label, and here's the quoted line. It started six weeks after the drug. After the drug was stopped, ALT went from 186 down to 31. Objective evidence: ALT was 186 on the day of onset. That's a score of 5, probable. A reviewer would have spent ten minutes building this."
5. **Data tab** (5s): "And here's the raw record it came from, so nothing is a black box."
6. **Swipe right / press →** (5s): "Agree. Next case. Z undoes it."
7. **Insights → knowledge graph, hover a solid line** (10s, optional)
   "Solid lines are possible reactions. Dashed lines mean the drug was prescribed *for* that condition, so we never count it as a side effect."

**Backup:** if the live demo fails, walk through the screenshots in `docs/images/`. In order: `ui-insights`, `ui-card-front`, `ui-card-drug`, `ui-card-reasons`, `ui-swipe`, `ui-knowledge-graph`.

---

## Likely judge questions

**"Why not just ask an LLM?"**
An LLM can't be audited and won't give the same answer twice. Druggie's scores are deterministic and every point comes with a reason. The AI draft is optional, cites evidence IDs (E1, E2…), is told never to invent data, and is labelled a draft.

**"The data is synthetic. How do we know it works?"**
Synthea never makes a drug cause anything, so we planted known reactions with an answer key, like amiodarone liver injury, and checked that the tool finds them. The answer key is never shown in the app. Real trial data with dates is where the population signals become meaningful. The loader for trial tables already exists (`python -m analytics --supabase`).

**"Why only 6 of 10 Naranjo questions?"**
The other four need things the record doesn't hold: alternative causes, placebo response, drug levels and dose response. We'd rather leave them blank than guess.

**"What's PRR?"**
The proportional reporting ratio: how often the condition shows up in people on the drug, divided by how often it shows up in people not on it. A pair counts as a signal at PRR ≥ 2 with at least 3 people and χ² ≥ 4 (Evans criteria), the same screen FDA and EMA use on spontaneous reports.

**"How do you avoid blaming a drug for what it was treating?"**
Each drug's reason for prescription comes from the record. Those links are drawn as dashed lines and excluded from signals. Metformin is never flagged for diabetes.

**"Does it replace the reviewer?"**
No. It never files a report and never makes the causality call. It cuts the gathering time and puts the strongest cases first.

**"How fast is it?"**
The scoring runs offline as a batch, and the app loads two static JSON files. Reviewing a card is a flip and a swipe. (Only quote a seconds-per-case number if you've actually timed it.)

---

## Before you present: checklist

- [ ] App runs from a clean clone (`npm install && npm run dev`)
- [ ] Fresh browser profile, so no saved decisions
- [ ] `.env` has a working key if you'll show the AI draft, and you've tested it on the amiodarone case
- [ ] Screen zoom set so the card is readable from the back of the room (Cmd + a couple of times)
- [ ] Screenshots open in a tab as a fallback
- [ ] One person speaks and one person drives the demo
