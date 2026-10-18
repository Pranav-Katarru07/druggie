# Druggie

**Swipe through drug-safety cases the way a reviewer actually thinks. The evidence is laid out, the strongest leads come first, and the doctor makes the call.**

Built at HackHarvard 2026 for the Regeneron "Reinvent Clinical Trials" challenge (Sus or Not).

---

## The problem

When a patient in a clinical trial has a serious adverse event, a drug-safety physician has to answer one question: **did the drug cause this?**

That answer has a deadline. If the event is serious, unexpected and possibly related, it is a SUSAR. The sponsor must report it to the FDA within **15 calendar days**, or **7 days** if it was fatal or life-threatening ([21 CFR 312.32](https://www.ecfr.gov/current/title-21/chapter-I/subchapter-D/part-312/subpart-B/section-312.32)).

Today that judgement is slow and inconsistent:

- **It is manual.** The reviewer reads the case, lists every drug the patient was on, opens each FDA label, checks the timeline, looks for labs, and scores it by hand.
- **Reviewers disagree.** Across 913 adverse reactions, two standard scoring methods (Naranjo and WHO-UMC) showed poor agreement, with a kappa of 0.143 ([Belhekar et al., 2014](https://pmc.ncbi.nlm.nih.gov/articles/PMC3912795/)). In another study of 100 cases they agreed only 55% of the time (*Korean Journal of Medicine*, 2008).
- **It takes time per case.** In the same 2014 study, a WHO-UMC assessment took 4.1 minutes per case and a Naranjo assessment took 10.3 minutes. Those minutes come before any writing, and every case sits on a regulatory clock.
- **The evidence is scattered.** The timeline lives in one system, the labels in another, the labs in a third. Nothing tells the reviewer which case or which drug to look at first.

## What Druggie does

Druggie puts each case on a card. One look tells the reviewer who the patient is and what happened. One flip shows why a drug is suspected.

### 1. A review deck, sorted by the likely cause
Cases are grouped by the drug most likely to have caused the event. A reviewer opens a deck (for example, *Epoetin alfa*) and works through it card by card.

- **Front of the card:** the patient, what went wrong, when it started, symptoms, BMI, blood pressure, smoking and existing conditions.
- **Back of the card:** the suspected drug, its FDA label warnings, the scored reasons, the cleaned source data and population insights.
- **Decide in one motion:** swipe right (or →) to agree that this drug is the most likely cause, swipe left (or ←) to disagree. Press Z to undo.

### 2. Naranjo scoring, done for you, with the reason for every answer
Each drug on each case is scored against the Naranjo questions that the data can answer. Every answer shows the evidence behind it:

| # | Question | How Druggie answers it |
|---|---|---|
| 1 | Is this a known reaction? | Searches the drug's FDA label (boxed warning, warnings, adverse reactions) |
| 2 | Did it start after the drug? | Compares the drug start date with the onset date |
| 3 | Did it improve after stopping? | Checks whether the problem ended after the drug stopped |
| 4 | Did it come back on restarting? | Looks for a later course of the same drug or drug class |
| 8 | A similar reaction before? | Searches the patient's history for the same reaction on a related drug |
| 10 | Objective evidence? | Looks for abnormal lab results around the onset date |

The questions that need clinical judgement (other causes, placebo response, drug levels, dose response) are left to the reviewer on purpose.

### 3. Population insights: what to look at first
Druggie compares every case against the whole patient population it came from:

- **Swipe these first.** Each case gets a 0 to 100 priority, based on how strongly its drug and symptom are linked across the population and how unusual the case is. The strongest leads rise to the top of the queue.
- **Groups of similar patients.** PCA and k-means clustering place every patient on a map by their drugs and conditions. Each group is labelled by what sets it apart, for example *clopidogrel · ischemic heart disease · nitroglycerin*.
- **Drug → condition signals.** Druggie flags pairs where people on a drug developed a condition at least twice as often as people not on it. It uses the proportional reporting ratio (PRR) with the Evans criteria, the same disproportionality test regulators use.
- **A knowledge graph.** Drugs and conditions appear as circles. Solid lines mark possible reactions and dashed lines mark what a drug was prescribed for. Hover over any circle or line for a plain-English explanation with real numbers, for example "5 of 10 people on epoetin alfa got chronic kidney disease stage 4, compared with 2% of people not on it". Tap a circle to jump straight to the review cases that involve it.
- **On every card.** The card's Insights tab shows the same comparison for that patient: how often the symptom appears on the drug versus off it, which group the patient belongs to, and which other cases look alike.

### 4. An AI draft, kept on a short leash
The **AI suggestion** button sends the case's evidence to a language model (Gemini by default, or any OpenAI-compatible model). The model drafts which drug best explains the picture, with every reason citing the evidence it came from. The API key stays on the server and never reaches the browser.

## Why this helps doctors

| Today | With Druggie |
|---|---|
| Open several systems to rebuild one timeline | Timeline, labels, labs and history on one card |
| Look up each drug's label by hand | Matching label text found and quoted |
| Score Naranjo questions from memory | Six questions pre-answered, each with its reason |
| Review cases in arrival order | Strongest population signals first |
| Easy to blame a drug for what it was treating | Prescribed-for links shown and excluded from signals |
| Hard to see patterns across patients | Clusters and a knowledge graph show them |

**The doctor still decides.** Druggie never files a report and never makes a causality call. It does the gathering and the sorting, so the reviewer spends their time on judgement instead of searching.

## How it works

```
Synthea patients (CSV)            openFDA drug labels      RxNorm (NLM)
        │                                │                     │
        └────────────► synthea_pipeline.py ◄───────────────────┘
                         cases, cleaned data, Naranjo answers
                                     │
                     frontend/public/data.json
                                     │
         analytics/ (python -m analytics) ──► frontend/public/insights.json
           PCA · k-means · PRR signals · knowledge graph · priority
                                     │
                  React app (Vite): Review · Patients · Insights
                                     │
                  server.py ──► LLM for the optional AI draft
```

| Part | What it does |
|---|---|
| `synthea_pipeline.py` | Turns Synthea patients into cases: each new problem plus the drugs taken at the time. Merges refills into courses, finds labels and drug classes, and answers the Naranjo questions |
| `extractData.py` | Shared helpers for openFDA labels and RxNorm, and an FAERS sample (`faers.json`) |
| `cases/planted_events.json` | Known true adverse events added on top of Synthea, because Synthea drugs never cause conditions. They give the tool something real to find. Their answer key is never shown in the app |
| `analytics/` | Population insights: name cleaning, clustering, signals, knowledge graph and priority. See [analytics/README.md](analytics/README.md) |
| `server.py` | Small backend for the AI suggestion. Keeps the API key off the browser |
| `frontend/` | The React app |

## Run it

You need **Node.js 20.19 or newer**. Python 3.11 or newer is optional, for the AI draft and for regenerating data.

```bash
git clone https://github.com/frayyan-rgb/druggie
cd druggie/frontend
npm install
npm run dev
```

Open the link it prints (usually http://localhost:5173). The repo already includes the case data and insights, so the app works straight away.

**Optional: the AI suggestion button**
```bash
cp .env.example .env          # then paste your key after LLM_API_KEY=
python server.py              # in a second terminal, from the repo root
```
A free Gemini key works (see `.env.example`). Groq and OpenRouter work too.

**Optional: regenerate the data from your own Synthea run**
```bash
# put Synthea CSV output in synthea/output/csv
python synthea_pipeline.py                     # rebuilds frontend/public/data.json
pip install -r analytics/requirements.txt
python -m analytics                            # rebuilds frontend/public/insights.json
python -m pytest analytics -q                  # tests
```

## Data and privacy

- **No real patient data.** Patients come from [Synthea](https://github.com/synthetichealth/synthea), a synthetic patient generator.
- **Public reference data only:** [openFDA drug labels](https://open.fda.gov/apis/drug/label/), [openFDA FAERS](https://open.fda.gov/apis/drug/event/) and [RxNorm](https://lhncbc.nlm.nih.gov/RxNav/).
- **Secrets stay local.** API keys live in `.env` files, which git ignores. Only the server-side script uses them.

## Limits, stated plainly

- **Patterns are not proof.** A signal means a drug and a condition appear together more often than expected. It does not mean the drug caused it.
- **Synthea is synthetic.** Its drugs never cause conditions, so the population signals in the demo data come from how Synthea simulates care. The planted events stand in for real reactions.
- **Six of ten Naranjo questions are automated.** The rest need a clinician.
- **This is a prototype for decision support,** not a medical device. Every causality decision belongs to a qualified reviewer.

## License

Released under the [MIT License](LICENSE).
