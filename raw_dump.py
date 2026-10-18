"""Print the raw source data behind a case: the patient's Synthea CSV rows and
each drug's openFDA label, unprocessed, to see which fields could help identify
the drug. Used by server.py's /api/log when a card or patient is opened.

Terminal output is trimmed (rows near the case date, label fields cut to
FIELD_CHARS); the full untrimmed data is written to raw_logs/<case id>/.
"""
import csv
import json
import os
from collections import defaultdict
from datetime import date

from synthea_pipeline import CSV_DIR, label_for

ROOT = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(ROOT, "raw_logs")
WINDOW_DAYS = {"medications": 365, "conditions": 365, "observations": 30, "encounters": 30, "procedures": 30}
FIELD_CHARS = 300      # label text shown per field in the terminal
TABLES = ["patients", "conditions", "medications", "allergies", "observations", "encounters", "procedures"]

_rows = None  # {table: {patient id: [row, ...]}}, loaded once


def rows_for(patient_id):
    global _rows
    if _rows is None:
        _rows = {}
        for table in TABLES:
            by_patient = defaultdict(list)
            with open(os.path.join(CSV_DIR, f"{table}.csv"), newline="") as f:
                for row in csv.DictReader(f):
                    by_patient[row.get("PATIENT") or row.get("Id")].append(row)
            _rows[table] = by_patient
    return {t: _rows[t].get(patient_id, []) for t in TABLES}


def row_date(row):
    value = row.get("START") or row.get("DATE") or ""
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def near(rows, onset, days):
    """Rows within `days` of the case date, or still running (no stop date / stop after) at that date."""
    keep = []
    for r in rows:
        d = row_date(r)
        stop = r.get("STOP", "")[:10]
        running = "STOP" in r and d and d <= onset and (not stop or date.fromisoformat(stop) >= onset)
        if running or (d and abs((d - onset).days) <= days):
            keep.append(r)
    return keep


def show_rows(title, rows, total=None):
    lines = [f"\n--- {title}: {len(rows)} row(s)" + (f" shown of {total}" if total is not None and total != len(rows) else "")]
    if rows:
        cols = [c for c in rows[0].keys() if any(r.get(c) for r in rows)]  # skip columns that are always empty
        lines.append("    " + " | ".join(cols))
        for r in rows:
            lines.append("    " + " | ".join(r.get(c, "") for c in cols))
    return lines


def flatten_label(label):
    """Every label field as (name, text), openfda metadata included."""
    out = []
    for key, value in label.items():
        if key == "openfda":
            for k, v in value.items():
                out.append((f"openfda.{k}", ", ".join(map(str, v)) if isinstance(v, list) else str(v)))
        else:
            out.append((key, " ".join(map(str, value)) if isinstance(value, list) else str(value)))
    return out


def dump_case(case, event):
    person = case.get("person_id")
    onset = date.fromisoformat(case["onset"]) if case.get("onset") else None
    case_dir = os.path.join(OUT_DIR, case["id"])
    os.makedirs(case_dir, exist_ok=True)

    lines = [f"\n{'#' * 72}", f"{event}: case {case['id']}  ({case.get('name', '')})"]
    lines.append(f"Full raw data saved to raw_logs/{case['id']}/")

    # ---- Synthea CSV rows ----
    if person:
        data = rows_for(person)
        with open(os.path.join(case_dir, "synthea_rows.json"), "w") as f:
            json.dump(data, f, indent=2)
        lines.append(f"\n===== SYNTHEA CSV ROWS (patient {person}) =====")
        lines += show_rows("patients.csv", data["patients"])
        lines += show_rows("allergies.csv", data["allergies"])
        for table in ("conditions", "medications", "observations", "encounters", "procedures"):
            rows, days = data[table], WINDOW_DAYS[table]
            if table == "observations":
                rows = [r for r in rows if r.get("CATEGORY") == "laboratory"]
            shown = near(rows, onset, days) if onset else rows
            if table == "conditions":
                # every medical disorder ever, plus anything (incl. social findings) near the case date
                shown = [r for r in rows if r["DESCRIPTION"].endswith("(disorder)") or r in shown]
                title = f"conditions.csv (all disorders + anything within {days} days)"
            else:
                title = f"{table}.csv (within {days} days of {onset})"
            lines += show_rows(title, shown, total=len(data[table]))

    # ---- openFDA labels, one per drug in the case ----
    lines.append("\n===== OPENFDA DRUG LABELS (raw) =====")
    meds = rows_for(person)["medications"] if person else []
    for drug in case["drugs"]:
        code = next((m["CODE"] for m in meds if m["DESCRIPTION"] == drug["name"]), None)
        label, via = label_for({"code": code, "description": drug["name"]})
        lines.append(f"\n--- {drug['name']}  (RxNorm code {code or 'none'})")
        if not label:
            lines.append("    No label found in openFDA.")
            continue
        safe = "".join(ch if ch.isalnum() else "_" for ch in drug["name"])[:60]
        with open(os.path.join(case_dir, f"label_{safe}.json"), "w") as f:
            json.dump(label, f, indent=2)
        if via:
            lines.append(f"    (matched by {via})")
        for key, text in flatten_label(label):
            text = " ".join(text.split())
            lines.append(f"    {key}: {text[:FIELD_CHARS]}{'…' if len(text) > FIELD_CHARS else ''}")

    return "\n".join(lines)
