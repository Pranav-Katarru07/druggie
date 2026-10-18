"""Build frontend/public/insights.json for the swipe app.

  pip install -r analytics/requirements.txt

  python -m analytics                                   # Synthea CSVs in synthea/output/csv + the app's cases
  python -m analytics --supabase                        # the team's clinical_trials / trial_participants tables
  python -m analytics --trials-csv trial_participants.csv
  python -m analytics --upload                          # also save the result to Supabase (table: insights)

Supabase options read SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY from .env (same file server.py uses).
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.request

from . import loaders
from .model import build

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_SYNTHEA = os.path.join(ROOT, "synthea", "output", "csv")
DEFAULT_CASES = os.path.join(ROOT, "frontend", "public", "data.json")
DEFAULT_OUT = os.path.join(ROOT, "frontend", "public", "insights.json")


def env(key):
    path = os.path.join(ROOT, ".env")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith(f"{key}=") and not line.startswith("#"):
                    value = line.split("=", 1)[1].strip()
                    if value:
                        return value
    return os.environ.get(key, "")


def supabase_creds():
    url, key = env("SUPABASE_URL"), env("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        sys.exit("Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY in .env (Supabase: Project Settings -> API).")
    return url.rstrip("/"), key


def upload(result):
    url, key = supabase_creds()
    req = urllib.request.Request(
        f"{url}/rest/v1/insights?on_conflict=id",
        data=json.dumps([{"id": "latest", "data": result}]).encode(),
        method="POST",
        headers={"apikey": key, "Authorization": f"Bearer {key}", "Content-Type": "application/json",
                 "Prefer": "resolution=merge-duplicates,return=minimal"},
    )
    try:
        urllib.request.urlopen(req, timeout=60).close()
    except urllib.error.HTTPError as e:
        hint = " Run analytics/insights_table.sql in the Supabase SQL Editor first." if e.code == 404 else ""
        sys.exit(f"Upload failed ({e.code}): {e.read().decode(errors='replace')[:300]}{hint}")
    print("Uploaded to Supabase table insights (id = latest).")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m analytics", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--synthea", metavar="DIR", help=f"Synthea CSV folder (default: {os.path.relpath(DEFAULT_SYNTHEA, ROOT)})")
    src.add_argument("--supabase", action="store_true", help="read clinical_trials + trial_participants from Supabase")
    src.add_argument("--trials-csv", metavar="FILE", help="CSV export: patient_id, all_medications, adverse_events, trial_name")
    ap.add_argument("--cases", metavar="FILE", default=DEFAULT_CASES, help="the app's data.json (cases to annotate)")
    ap.add_argument("--out", metavar="FILE", default=DEFAULT_OUT)
    ap.add_argument("--upload", action="store_true", help="also save to Supabase table insights")
    ap.add_argument("--limit", type=int, help="only use the first N population patients (quick tests)")
    ap.add_argument("--min-support", type=int, default=2, help="ignore drugs/conditions seen in fewer patients (default 2)")
    ap.add_argument("--min-signal-n", type=int, default=3, help="patients needed before a pair can be a signal (default 3)")
    ap.add_argument("--window-days", type=int, default=90, help="condition must start this soon after the drug (default 90)")
    ap.add_argument("--clusters", type=int, help="number of groups (default: picked automatically)")
    args = ap.parse_args(argv)

    if args.supabase:
        try:
            population, source = loaders.supabase_trials(*supabase_creds()), "supabase: trial_participants"
        except urllib.error.HTTPError as e:
            sys.exit(f"Supabase said {e.code}: {e.read().decode(errors='replace')[:300]}\n"
                     "  -> Check SUPABASE_SERVICE_ROLE_KEY, and that clinical_trials / trial_participants exist.")
        except urllib.error.URLError as e:
            sys.exit(f"Couldn't reach Supabase ({e.reason}). Check SUPABASE_URL in .env and your internet connection.")
    elif args.trials_csv:
        population, source = loaders.trial_csv(args.trials_csv), f"csv: {os.path.basename(args.trials_csv)}"
    else:
        folder = args.synthea or DEFAULT_SYNTHEA
        if not os.path.exists(os.path.join(folder, "medications.csv")):
            sys.exit(f"No Synthea CSVs in {folder}. Pass --synthea DIR, --supabase or --trials-csv FILE.")
        population, source = loaders.synthea_csv(folder), f"synthea: {os.path.relpath(folder, ROOT)}"
    if args.limit:
        population = sorted(population, key=lambda p: p.id)[: args.limit]

    cases = loaders.druggie_cases(args.cases) if args.cases and os.path.exists(args.cases) else []
    print(f"population: {len(population)} patients   cases to annotate: {len(cases)}")

    result = build(population, cases, min_support=args.min_support, min_signal_n=args.min_signal_n,
                   window_days=args.window_days, k=args.clusters, source=source)
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, separators=(",", ":"))
    c = result["counts"]
    print(f"groups: {result['params']['clusters']}   signals: {c['signals']}   features: {c['features']}")
    for cl in result["clusters"]:
        print(f"  group {cl['id'] + 1} ({cl['size']} patients): {cl['label']}")
    print(f"wrote {os.path.relpath(args.out, ROOT)} ({os.path.getsize(args.out) // 1024} KB)")
    if args.upload:
        upload(result)


if __name__ == "__main__":
    main()
