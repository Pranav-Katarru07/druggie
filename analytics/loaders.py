"""Read patients from wherever the team keeps them, into one simple shape.

Every loader returns a list of Patient records:
  id          patient id
  trial       trial name (or None)
  drugs       {drug name: (start, stop)}   dates are datetime.date or None
  conditions  {condition name: onset}       onset is datetime.date or None
  indications {(drug, condition)}           conditions the drug was prescribed FOR (Synthea REASONDESCRIPTION)

Sources:
  supabase_trials()  the team's Supabase tables clinical_trials + trial_participants
  trial_csv()        a CSV export of trial_participants (columns: patient_id, all_medications, adverse_events, trial_name)
  synthea_csv()      a Synthea CSV output folder (medications.csv, conditions.csv) - has dates and indications
  druggie_json()     frontend/public/data.json from extractData.py
"""
import csv
import json
import os
import urllib.request
from dataclasses import dataclass, field
from datetime import date

from .normalize import condition_name, drug_names

csv.field_size_limit(2**31 - 1)


@dataclass
class Patient:
    id: str
    trial: str | None = None
    drugs: dict = field(default_factory=dict)        # name -> (start, stop)
    conditions: dict = field(default_factory=dict)   # name -> onset
    indications: set = field(default_factory=set)    # {(drug, condition)}


def _date(value) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _add_drug(p: Patient, raw: str, start=None, stop=None, reason: str | None = None):
    for name in drug_names(raw):
        # Repeat prescriptions: keep the widest exposure window. No stop date = still taking it.
        if name in p.drugs:
            old_start, old_stop = p.drugs[name]
            start = min(filter(None, [old_start, start]), default=None)
            stop = None if old_stop is None or stop is None else max(old_stop, stop)
        p.drugs[name] = (start, stop)
        cond = condition_name(reason) if reason else None
        if cond:
            p.indications.add((name, cond))


def _add_condition(p: Patient, raw: str, onset=None):
    name = condition_name(raw)
    if not name:
        return
    old = p.conditions.get(name)
    p.conditions[name] = min(filter(None, [old, onset]), default=None)


def _as_list(value) -> list[str]:
    """Postgres arrays arrive as JSON lists from the API, or as '["a","b"]' / '{a,b}' strings in CSV exports."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    text = str(value).strip()
    if text.startswith("["):
        return [str(v) for v in json.loads(text)]
    if text.startswith("{") and text.endswith("}"):
        return [v.strip().strip('"') for v in next(csv.reader([text[1:-1]], skipinitialspace=True))]
    return [text] if text else []


def from_trial_rows(rows: list[dict]) -> list[Patient]:
    """Rows shaped like trial_participants (+ trial_name). Lists only, no dates."""
    patients: dict[str, Patient] = {}
    for r in rows:
        pid = str(r["patient_id"])
        p = patients.setdefault(pid, Patient(id=pid, trial=r.get("trial_name")))
        for m in _as_list(r.get("all_medications")):
            _add_drug(p, m)
        for c in _as_list(r.get("adverse_events")):
            _add_condition(p, c)
    return list(patients.values())


def trial_csv(path: str) -> list[Patient]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return from_trial_rows(list(csv.DictReader(f)))


def _get_all(base: str, key: str, table: str, select: str) -> list[dict]:
    rows, start, page = [], 0, 1000
    while True:
        req = urllib.request.Request(
            f"{base}/rest/v1/{table}?select={select}",
            headers={"apikey": key, "Authorization": f"Bearer {key}", "Range-Unit": "items",
                     "Range": f"{start}-{start + page - 1}"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            batch = json.loads(resp.read())
        rows += batch
        if len(batch) < page:
            return rows
        start += page


def supabase_trials(base: str, key: str) -> list[Patient]:
    """Read the team's clinical_trials + trial_participants tables."""
    base = base.rstrip("/")
    trials = {t["id"]: t["trial_name"] for t in _get_all(base, key, "clinical_trials", "id,trial_name")}
    rows = _get_all(base, key, "trial_participants", "patient_id,trial_id,all_medications,adverse_events")
    for r in rows:
        r["trial_name"] = trials.get(r.get("trial_id"))
    return from_trial_rows(rows)


def synthea_csv(folder: str, limit: int | None = None) -> list[Patient]:
    """Synthea's CSV export. Gives real start/stop dates and the reason each drug was prescribed."""
    patients: dict[str, Patient] = {}

    def get(pid):
        return patients.setdefault(pid, Patient(id=pid))

    with open(os.path.join(folder, "medications.csv"), encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            _add_drug(get(r["PATIENT"]), r["DESCRIPTION"], _date(r["START"]), _date(r["STOP"]), r.get("REASONDESCRIPTION"))
    with open(os.path.join(folder, "conditions.csv"), encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            _add_condition(get(r["PATIENT"]), r["DESCRIPTION"], _date(r["START"]))
    out = [p for p in patients.values() if p.drugs]
    return out[:limit] if limit else out


@dataclass
class Case:
    """One swipe card from frontend/public/data.json: a person, the problem(s) that began together, their drugs."""
    id: str
    person_id: str
    reactions: list            # clean condition names
    drugs: dict                # raw drug name as shown in the app -> list of ingredient names
    profile: Patient           # the case as a Patient, for placing it on the cluster map


def druggie_cases(path: str) -> list[Case]:
    """frontend/public/data.json, written by synthea_pipeline.py."""
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    cases = []
    for row in data:
        person = row.get("person_id") or row["id"]
        profile = Patient(id=row["id"])
        drugs = {}
        for d in row.get("drugs", []):
            drugs[d["name"]] = drug_names(d["name"])
            _add_drug(profile, d["name"], _date(d.get("started")), _date(d.get("stopped")))
        onset = _date(row.get("onset"))
        reactions = []
        for r in row.get("reactions", []):
            name = condition_name(r)
            if name:
                reactions.append(name)
                _add_condition(profile, r, onset)
        for r in (row.get("details") or {}).get("existing_conditions", []):
            _add_condition(profile, r)
        cases.append(Case(id=row["id"], person_id=person, reactions=reactions, drugs=drugs, profile=profile))
    return cases
