# druggie insights: clusters, signals, knowledge graph

The swipe deck shows a handful of cases. This folder looks at the **whole population** those cases come from
(every Synthea patient, or every trial participant) and tells the doctor, for each card:

| Question | Method | Where it shows |
|---|---|---|
| Which group of similar patients is this person in? | PCA + k-means on each patient's drugs and conditions | Insights page map, card "Insights" tab |
| Across everyone, do people on this drug get this symptom more often? | Disproportionality (PRR with the Evans criteria used in pharmacovigilance) | Card "Insights" tab, signals table |
| How do drugs and conditions connect? | Knowledge graph: possible reaction, prescribed for, taken together | Insights page |
| Which cards should be swiped first? | Priority 0-100 from signal strength and how unusual the case is | "Swipe these first" |

It decides **what to look at first**. It never decides what caused what.

## Run it

```bash
pip install -r analytics/requirements.txt        # numpy + scikit-learn

python -m analytics                               # Synthea CSVs in synthea/output/csv (same folder synthea_pipeline.py uses)
python -m analytics --supabase                    # our Supabase tables clinical_trials + trial_participants
python -m analytics --trials-csv participants.csv # a CSV export: patient_id, all_medications, adverse_events, trial_name
```

It writes `frontend/public/insights.json`. Then `cd frontend && npm run dev` and open **Insights**, or flip any card
and open its **Insights** tab. If the file is missing the app still works; the insight panels just say so.

Useful options: `--window-days 90` (a condition must start this soon after the drug),
`--min-signal-n 3`, `--clusters 6` (otherwise picked automatically), `--limit 500` (quick test).

## Plugging in our data

**Best: Synthea CSVs** (`synthea/output/csv`). They have start/stop dates and the reason each drug was prescribed,
so the signals are the most trustworthy: a condition only counts if it began after the drug started,
and a drug's own reason for use (metformin → diabetes) is never counted as a reaction.

**Supabase trial tables.** Put these in the root `.env` (server-side only, never in `frontend/`):
```
SUPABASE_URL=https://ycfhbflkkgyazjilomvv.supabase.co
SUPABASE_SERVICE_ROLE_KEY=...
```
`trial_participants` currently has lists without dates, so every condition the person ever had counts and
confounding is likely. To make the trial data as strong as the Synthea CSVs, export:
1. one row per medication course with `start` and `stop` dates,
2. conditions with an onset date,
3. the reason each drug was prescribed, when known.

**Share results through Supabase (optional).** Run `analytics/insights_table.sql` once in the SQL Editor, then
`python -m analytics --upload`. The app reads from Supabase when `frontend/.env.local` has
`VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`, otherwise from `insights.json`.

## Files

| File | What it does |
|---|---|
| `normalize.py` | Cleans names: "24 HR Metformin hydrochloride 500 MG..." → `metformin`; drops "Full-time employment (finding)" and other social entries |
| `loaders.py` | Reads Synthea CSVs, Supabase trial tables, CSV exports and the app's `data.json` into one shape |
| `model.py` | Features → PCA map → k-means groups; PRR signals; knowledge graph; case priority |
| `__main__.py` | The command line above |
| `test_analytics.py` | `python -m pytest analytics -q` |
| `../frontend/src/insights/` | Cluster map, knowledge graph, card panel; `../frontend/src/pages/InsightsPage.tsx` |

## How the numbers work

- **Features.** Each patient is a row of yes/no: takes drug X, has condition Y. Things almost everyone has count for less (IDF weighting).
- **PCA** squeezes hundreds of columns into 2 numbers for the map. The page says which drugs and conditions drive each axis.
- **Groups** are k-means on 10 PCA dimensions; the number of groups is the one with the best silhouette score (2-8).
  Each group is named after what is much more common in it than overall.
- **Signal** = at least 3 people, PRR ≥ 2, chi-square ≥ 4 (Evans et al., 2001). PRR = (share of people on the drug who got the condition) ÷ (share of people not on it who got it).
- **Priority** = 70% strongest signal among the card's drug→symptom pairs + 30% how unusual the case is for its group.

## Read with care

Signals mean "together more often than expected", not "caused by". Synthea drugs never cause conditions, so signals in
Synthea data come from how it simulates care (e.g. heart drugs and heart imaging findings). Real trial data with dates
is where this becomes meaningful.
