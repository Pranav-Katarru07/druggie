"""Turn Synthea patients into cases for the app.

Each case is one new medical problem (condition onset) plus the drugs the
patient was taking at the time. For every drug we collect reasons for and
against it being the cause, using the same label checks as extractData.py
plus the checks Synthea's dates make possible: timing, stopping the drug
(dechallenge), restarting it (rechallenge) and whether it was prescribed to
treat that very condition.

Synthea never makes a drug cause a condition, so real adverse events must be
planted (cases/planted_events.json) for the tool to have anything true to find.

Run:  python3 synthea_pipeline.py   (writes frontend/public/data.json)
"""
import csv
import json
import os
import urllib.parse
from collections import defaultdict
from datetime import date, datetime

from extractData import (cached_search, fetch_json, find_in_label, is_clinical,
                         rxnorm_ingredients, section_text)

ROOT = os.path.dirname(os.path.abspath(__file__))
CSV_DIR = os.path.join(ROOT, "synthea", "output", "csv")
PLANTED_FILE = os.path.join(ROOT, "cases", "planted_events.json")
OUT_FILE = os.path.join(ROOT, "frontend", "public", "data.json")

RECENT_DAYS = 90        # a drug started this close before onset counts as "New"
COURSE_GAP_DAYS = 30    # refills closer than this are merged into one course
DECHALLENGE_DAYS = 60   # condition resolving within this after stopping = positive dechallenge
SEX = {"M": "Male", "F": "Female"}

# Problems a drug realistically can't cause; skipping them keeps the deck focused
# (dental ones come from Synthea's dental module, which prescribes fluoride right before each visit)
NOT_DRUG_RELATED = ["sprain", "fracture", "burn", "concussion", "laceration", "injury", "pregnancy",
                    "gingiv", "dental", "tooth", "teeth", "molars", "alveolitis of jaw"]


# ---------- loading ----------

def parse_date(value):
    return datetime.fromisoformat(value[:10]).date() if value else None


def read_csv(name):
    with open(os.path.join(CSV_DIR, name), newline="") as f:
        return list(csv.DictReader(f))


def build_courses(med_rows):
    """Merge each drug's dispensing rows into continuous courses of treatment."""
    by_drug = defaultdict(list)
    for m in med_rows:
        by_drug[m["DESCRIPTION"]].append(m)
    courses = []
    for desc, rows in by_drug.items():
        rows.sort(key=lambda m: m["START"])
        current = None
        for m in rows:
            start, stop = parse_date(m["START"]), parse_date(m["STOP"])
            if current and (current["stop"] is None or (start - current["stop"]).days <= COURSE_GAP_DAYS):
                current["stop"] = None if (current["stop"] is None or stop is None) else max(current["stop"], stop)
                continue
            current = {"description": desc, "code": m.get("CODE"), "start": start, "stop": stop,
                       "reason": m.get("REASONDESCRIPTION") or None}
            courses.append(current)
    return courses


def load_patients():
    patients = {p["Id"]: p for p in read_csv("patients.csv")}
    meds, conds = defaultdict(list), defaultdict(list)
    for m in read_csv("medications.csv"):
        meds[m["PATIENT"]].append(m)
    for c in read_csv("conditions.csv"):
        conds[c["PATIENT"]].append({"description": c["DESCRIPTION"], "start": parse_date(c["START"]),
                                    "stop": parse_date(c["STOP"]), "planted": False})
    courses = {pid: build_courses(rows) for pid, rows in meds.items()}

    # Add planted adverse events on top of the Synthea history
    if os.path.exists(PLANTED_FILE):
        with open(PLANTED_FILE) as f:
            for event in json.load(f):
                pid, d, c = event["patient_id"], event["drug"], event["condition"]
                courses.setdefault(pid, []).append({"description": d["description"], "code": d.get("code"),
                                                    "start": parse_date(d["start"]), "stop": parse_date(d.get("stop")),
                                                    "reason": d.get("reason")})
                conds[pid].append({"description": c["description"], "start": parse_date(c["start"]),
                                   "stop": parse_date(c.get("stop")), "planted": True})
    return patients, courses, conds


# ---------- labels ----------

_rxcui_cache = {}


def label_for(course):
    """Synthea gives an RxNorm code for every drug, so try that before any name matching."""
    key = course["code"] or course["description"]
    if key in _rxcui_cache:
        return _rxcui_cache[key]
    label, via = None, None
    if course["code"]:
        url = ("https://api.fda.gov/drug/label.json?search="
               + urllib.parse.quote_plus(f'openfda.rxcui:"{course["code"]}"') + "&limit=1")
        data = fetch_json(url)
        if data and data.get("results"):
            label = data["results"][0]
    if not label:
        # Ingredient via RxNorm: from the code if we have one, else from the name
        ingredients = []
        if course["code"]:
            related = fetch_json(f"https://rxnav.nlm.nih.gov/REST/rxcui/{course['code']}/related.json?tty=IN")
            groups = (related or {}).get("relatedGroup", {}).get("conceptGroup") or []
            ingredients = [c["name"] for g in groups for c in g.get("conceptProperties", [])]
        for ing in ingredients or rxnorm_ingredients(course["description"].split(" ")[0]):
            label = cached_search(ing)
            if label:
                via = f"ingredient {ing}, via RxNorm"
                break
    _rxcui_cache[key] = (label, via)
    return label, via


# ---------- reasons for / against ----------

def clean(description):
    """'Acute bronchitis (disorder)' -> 'Acute bronchitis'"""
    return description.rsplit(" (", 1)[0] if description.endswith(")") else description


def courses_of(courses, description):
    return sorted((c for c in courses if c["description"] == description), key=lambda c: c["start"])


def reasons(course, condition, all_courses, all_conditions, active, labels):
    reaction = clean(condition["description"])
    onset, resolved = condition["start"], condition["stop"]
    label, via = labels[course["description"]]
    for_, against, unknown = [], [], []

    # Prescribed to treat this very condition: almost certainly treatment, not cause
    if course["reason"] and clean(course["reason"]).lower() == reaction.lower():
        against.append({"text": "This drug was prescribed to treat this condition, so it is likely treatment, not the cause."})

    # Known reaction (Naranjo Q1)
    if label is None:
        unknown.append({"text": "No label found, so it can't be checked whether this reaction is known for this drug."})
    else:
        hit = find_in_label(label, reaction)
        if hit:
            section, quote = hit
            serious = " (the label's most serious warning)" if section == "Boxed warning" else ""
            found = f" (found by {via})" if via else ""
            for_.append({"text": f"The label{found} lists this reaction under {section}{serious}.",
                         "section": section, "quote": quote})
        else:
            against.append({"text": "The reaction is not mentioned in the label sections checked."})

    # Timing (Naranjo Q2)
    days = (onset - course["start"]).days
    if days <= RECENT_DAYS:
        for_.append({"text": f"Started {days} days before the condition began, a typical window for a drug reaction."})
    else:
        unknown.append({"text": f"Taken for {days // 365} yr {days % 365 // 30} mo before onset; reactions this late are possible but less typical."})

    # Alternate causes (Naranjo Q5): other drugs whose labels mention the reaction
    others = [c["description"] for c in active if c["description"] != course["description"]
              and labels[c["description"]][0] and find_in_label(labels[c["description"]][0], reaction)]
    if others:
        against.append({"text": "Other drugs taken at the time also list this reaction: " + ", ".join(others) + "."})

    # Dechallenge (Naranjo Q3)
    stop = course["stop"]
    if stop and resolved and stop <= resolved and (resolved - stop).days <= DECHALLENGE_DAYS:
        for_.append({"text": f"The condition resolved {(resolved - stop).days} days after the drug was stopped."})
    elif resolved and (stop is None or stop > resolved):
        against.append({"text": "The condition resolved while the drug was still being taken."})
    elif stop and not resolved:
        against.append({"text": "The condition continued after the drug was stopped."})
    else:
        unknown.append({"text": "It's unclear whether stopping the drug changed the condition."})

    # Rechallenge (Naranjo Q4): drug restarted later; did the condition come back?
    later = [c for c in courses_of(all_courses, course["description"]) if c["start"] > (stop or onset)]
    if later:
        restart = later[0]["start"]
        recurred = any(c["description"] == condition["description"] and c["start"] > restart
                       and (c["start"] - restart).days <= RECENT_DAYS for c in all_conditions)
        if recurred:
            for_.append({"text": f"The drug was restarted on {restart} and the condition came back."})
        else:
            against.append({"text": f"The drug was restarted on {restart} and the condition did not come back."})
    else:
        unknown.append({"text": "The drug was not restarted, so re-exposure can't be checked."})

    return {"name": course["description"], "role": "New" if days <= RECENT_DAYS else "Ongoing",
            "for": for_, "against": against, "unknown": unknown}


# ---------- assembling cases ----------

def is_candidate_condition(c):
    d = c["description"].lower()
    return (c["planted"] or (d.endswith("(disorder)") and is_clinical(d)
                             and not any(w in d for w in NOT_DRUG_RELATED)))


def build_cases():
    patients, courses, conds = load_patients()
    cases = []
    for pid, p in patients.items():
        pcourses, pconds = courses.get(pid, []), conds.get(pid, [])
        # Group conditions that began on the same day into one case
        by_onset = defaultdict(list)
        for c in pconds:
            if is_candidate_condition(c):
                by_onset[c["start"]].append(c)

        for onset, group in sorted(by_onset.items()):
            active = [c for c in pcourses if c["start"] < onset and (c["stop"] is None or c["stop"] >= onset)]
            # Keep only cases where a drug was started recently (planted cases always kept)
            if not any(g["planted"] for g in group) and not any((onset - c["start"]).days <= RECENT_DAYS for c in active):
                continue
            # One entry per drug: the course that was running at onset
            seen, drugs_at_onset = set(), []
            for c in sorted(active, key=lambda c: c["start"], reverse=True):
                if c["description"] not in seen:
                    seen.add(c["description"])
                    drugs_at_onset.append(c)
            if not drugs_at_onset:
                continue

            labels = {c["description"]: label_for(c) for c in drugs_at_onset}
            assessment = []
            for cond in group:
                assessment.append({
                    "reaction": clean(cond["description"]),
                    "assessable": True,
                    "drugs": [reasons(c, cond, pcourses, pconds, drugs_at_onset, labels) for c in drugs_at_onset],
                })

            drugs = []
            for c in drugs_at_onset:
                label, via = labels[c["description"]]
                entry = {"name": c["description"], "role": "New" if (onset - c["start"]).days <= RECENT_DAYS else "Ongoing",
                         "indication": clean(c["reason"]) if c["reason"] else None,
                         "label_found": label is not None, "label_via": via,
                         "started": c["start"].isoformat(), "stopped": c["stop"].isoformat() if c["stop"] else None}
                if label:
                    entry["boxed_warning"] = section_text(label, "boxed_warning")
                    entry["warnings"] = section_text(label, "warnings_and_cautions") or section_text(label, "warnings")
                    entry["adverse_reactions"] = section_text(label, "adverse_reactions")
                drugs.append(entry)

            birth = parse_date(p["BIRTHDATE"])
            age = onset.year - birth.year - ((onset.month, onset.day) < (birth.month, birth.day))
            cases.append({
                "id": f"{pid[:8]}-{onset.isoformat()}",
                "age": str(age),
                "sex": SEX.get(p["GENDER"], "Unknown"),
                "onset": onset.isoformat(),
                "reactions": [clean(c["description"]) for c in group],
                "drugs": drugs,
                "assessment": assessment,
            })
            print(f"Case {cases[-1]['id']}: {', '.join(cases[-1]['reactions'])} | {len(drugs)} drugs")
    return cases


def main():
    if not os.path.isdir(CSV_DIR):
        raise SystemExit(f"No Synthea output at {CSV_DIR}. Run Synthea with --exporter.csv.export=true first.")
    cases = build_cases()
    with open(OUT_FILE, "w") as f:
        json.dump(cases, f, indent=2)
    print(f"Saved {len(cases)} cases to {os.path.relpath(OUT_FILE, ROOT)}")


if __name__ == "__main__":
    main()
