"""Turn Synthea patients into cases for the app.

Each case is one new medical problem (condition onset) plus the drugs the
patient was taking at the time. Each drug is then run through QUESTIONS (the
Naranjo questions, added one at a time) and gets a score from the answers.

Synthea never makes a drug cause a condition, so real adverse events must be
planted (cases/planted_events.json) for the tool to have anything true to find.

Run:  python3 synthea_pipeline.py   (writes frontend/public/data.json)
"""
import csv
import json
import os
import re
import urllib.parse
from collections import defaultdict
from datetime import date, datetime, timedelta

from extractData import cached_search, fetch_json, is_clinical, rxnorm_ingredients, section_text, snippet

ROOT = os.path.dirname(os.path.abspath(__file__))
CSV_DIR = os.path.join(ROOT, "synthea", "output", "csv")
PLANTED_FILE = os.path.join(ROOT, "cases", "planted_events.json")
OUT_FILE = os.path.join(ROOT, "frontend", "public", "data.json")

RECENT_DAYS = 90        # a drug started this close before onset counts as "New"
COURSE_GAP_DAYS = 30    # refills closer than this are merged into one course
SEX = {"M": "Male", "F": "Female"}

# Problems a drug realistically can't cause; skipping them keeps the deck focused
# (dental ones come from Synthea's dental module, which prescribes fluoride right before each visit)
NOT_DRUG_RELATED = ["sprain", "fracture", "burn", "concussion", "laceration", "injury", "pregnancy",
                    "gingiv", "dental", "tooth", "teeth", "molars", "alveolitis of jaw"]

# Lab tests that can measure a reaction: LOINC code -> (short name, normal low, normal high).
# Synthea stores values but no normal ranges, so these are typical adult limits.
LAB_TESTS = {
    "1742-6": ("ALT", None, 40),
    "1920-8": ("AST", None, 40),
    "1975-2": ("Bilirubin", None, 1.2),
    "2160-0": ("Creatinine", None, 1.3),
    "2823-3": ("Potassium", 3.5, 5.1),
    "2345-7": ("Glucose", 70, 140),
    "718-7": ("Hemoglobin", 12, None),
    "8480-6": ("Systolic BP", 90, 140),
}
# Words in a reaction's name -> the tests that measure it. Reactions with no match have no lab marker.
REACTION_LABS = [
    (("hepat", "liver"), ["1742-6", "1920-8", "1975-2"]),
    (("kidney", "renal", "nephr"), ["2160-0", "2823-3"]),
    (("hyperkal", "hypokal"), ["2823-3"]),
    (("diabet", "glyc"), ["2345-7"]),
    (("anemia", "anaemia"), ["718-7"]),
    (("hypertens", "hypotens"), ["8480-6"]),
]
# What the patient reported or showed near onset, for the front of the card.
# Measurements: LOINC code -> (label, shown when, text)
FELT_OBS = {
    "72514-3": (lambda v: v >= 1, lambda v: f"Pain {v:g}/10"),
    "8310-5": (lambda v: v >= 38, lambda v: f"Fever {v:g} °C"),
    "8867-4": (lambda v: v > 100, lambda v: f"Fast heart rate ({v:g}/min)"),
    "70274-6": (lambda v: v >= 5, lambda v: f"Anxiety (GAD-7 score {v:g})"),
    "55758-7": (lambda v: v >= 3, lambda v: f"Low mood (PHQ-2 score {v:g})"),
}
# Findings (conditions ending "(finding)") that describe how the patient feels, not their social situation
FELT_WORDS = ["pain", "ache", "stress", "fever", "cough", "nausea", "vomit", "fatigue", "tired", "headache", "dizz",
              "rash", "itch", "insomnia", "anxiety", "sore", "breath", "swelling", "wheez"]
FELT_WINDOW = (-7, 14)        # days around onset
# Patient details for the front of the card: latest reading in the year before onset
DETAIL_OBS = {"39156-5": "bmi", "8480-6": "systolic", "8462-4": "diastolic", "72166-2": "smoking"}
DETAIL_LOOKBACK_DAYS = 365
MARITAL = {"M": "Married", "S": "Single", "D": "Divorced", "W": "Widowed"}
# Health-related findings worth listing as existing conditions (the rest are social: employment, housing...)
HEALTH_FINDINGS = ["obesity", "prediabetes", "pain", "smokes", "alcohol", "anxiety", "misuses drugs"]
LAB_WINDOW = (-7, 120)        # days around onset kept in the lab trend table
EVIDENCE_WINDOW = (-7, 30)    # days around onset where an abnormal test counts as objective evidence (Q10)
# Reactions whose end date says little about the drug: infections clear anyway, staged diseases restage
UNRELIABLE_END = ["infection", "bronchitis", "sinusitis", "pharyngitis", "otitis", "cystitis", "pneumonia",
                  "streptococcal", "sore throat", "viral", "bacterial", "sepsis", "influenza", "covid", "stage"]


# ---------- loading ----------

def display_name(p):
    """Synthea appends digits to names ("Numbers230 Moen819"); drop them for display."""
    return " ".join(re.sub(r"\d+", "", p[k]) for k in ("FIRST", "LAST") if p.get(k)).strip()


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
                current["rows"] += 1
                continue
            current = {"description": desc, "code": m.get("CODE"), "start": start, "stop": stop,
                       "reason": m.get("REASONDESCRIPTION") or None, "rows": 1}
            courses.append(current)
    return courses


def load_patients():
    patients = {p["Id"]: p for p in read_csv("patients.csv")}
    meds, conds, labs, allergies = defaultdict(list), defaultdict(list), defaultdict(list), defaultdict(list)
    for m in read_csv("medications.csv"):
        meds[m["PATIENT"]].append(m)
    for c in read_csv("conditions.csv"):
        conds[c["PATIENT"]].append({"description": c["DESCRIPTION"], "code": c["CODE"], "start": parse_date(c["START"]),
                                    "stop": parse_date(c["STOP"]), "planted": False, "evidence": None})
    details = defaultdict(list)
    for o in read_csv("observations.csv"):
        if o["CODE"] in DETAIL_OBS:
            details[o["PATIENT"]].append({"date": parse_date(o["DATE"]), "key": DETAIL_OBS[o["CODE"]], "value": o["VALUE"]})
        if o["CODE"] in LAB_TESTS or o["CODE"] in FELT_OBS:
            labs[o["PATIENT"]].append({"date": parse_date(o["DATE"]), "code": o["CODE"],
                                       "value": float(o["VALUE"]), "units": o["UNITS"], "planted": False})
    for a in read_csv("allergies.csv"):
        if a["CATEGORY"] == "medication":
            allergies[a["PATIENT"]].append(a)
    courses = {pid: build_courses(rows) for pid, rows in meds.items()}

    # Add planted adverse events on top of the Synthea history
    if os.path.exists(PLANTED_FILE):
        with open(PLANTED_FILE) as f:
            for event in json.load(f):
                pid, d, c = event["patient_id"], event["drug"], event["condition"]
                courses.setdefault(pid, []).append({"description": d["description"], "code": d.get("code"),
                                                    "start": parse_date(d["start"]), "stop": parse_date(d.get("stop")),
                                                    "reason": d.get("reason"), "rows": 1})
                conds[pid].append({"description": c["description"], "code": None, "start": parse_date(c["start"]),
                                   "stop": parse_date(c.get("stop")), "planted": True,
                                   "evidence": c.get("objective_evidence")})
                for lab in event.get("labs", []):
                    labs[pid].append({**lab, "date": parse_date(lab["date"]), "planted": True})
                for s in event.get("symptoms", []):
                    conds[pid].append({"description": s["description"], "code": None, "start": parse_date(s["start"]),
                                       "stop": None, "planted": True, "evidence": None, "symptom": True})
    return patients, courses, conds, labs, allergies, details


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


def boxed_headline(label):
    """'WARNING: PULMONARY, HEPATIC and CARDIAC TOXICITY Pacerone is...' -> 'Pulmonary, hepatic and cardiac toxicity'"""
    text = " ".join((section_text(label, "boxed_warning", limit=None) or "").split())
    if not text:
        return None
    body = re.sub(r"^WARNINGS?:?\s*", "", text)
    capital = lambda w: w.upper() == w or re.fullmatch(r"[A-Z0-9-]+s", w)  # "ESAs" counts as capitalised
    words = []
    for w in body.split():
        if not (capital(w) or w in ("and", "or", "of", "with", "in", "the", "for")):
            break
        words.append(w)
    head = " ".join(words).strip(" .;:,•")
    if len(head) < 6:  # not a capitalised headline: use the first sentence
        return re.split(r"(?<=\.)\s", body)[0].rstrip(".")[:160]
    # Sentence case, keeping acronyms and gene names ("ESAs", "CYP2C19")
    out = " ".join(w if re.search(r"\d", w) or re.fullmatch(r"[A-Z]+s", w) else w.lower() for w in head.split())
    return out[0].upper() + out[1:]


def serious_side_effects(label):
    """Newer labels open Adverse reactions with 'The following serious adverse reactions are described...:
    Pulmonary Toxicity [see ...] Hepatic Injury [see ...]'. Returns those names, or []."""
    text = " ".join((section_text(label, "adverse_reactions", limit=None) or "").split())
    m = re.search(r"following (?:serious |clinically significant |important )?adverse reactions are "
                  # ends where a sentence starts ("The most common..."), not at "Photosensitivity and ..."
                  r"(?:described|discussed)[^:]*:\s*(.*?\])\s*(?:[A-Z][a-z]+ (?!(?:and|of|or)\b)[a-z]|\d+\.\d|$)",
                  text)
    if not m:
        return []
    items = [re.sub(r"\s*\(.*$", "", s).strip(" •,;") for s in re.split(r"\[[^\]]*\]", m.group(1))]
    return list(dict.fromkeys(s for s in items if s and len(s.split()) <= 8))[:10]


def common_side_effects(label):
    """The label's own 'most common adverse reactions are a, b, c' list, or [] if it doesn't state one."""
    text = " ".join((section_text(label, "adverse_reactions", limit=None) or "").split())
    m = re.search(r"most (?:common(?:ly reported)?|frequent(?:ly reported)?)[^.]{0,80}?"
                  r"(?:adverse (?:reactions|events)|side effects)([^.:]*?)(?:\bare\b|\bwere\b|\binclude\b|:)\s*([^.]+)", text, re.I)
    if not m or "discontinu" in m.group(1).lower():  # "most common reasons for stopping" is a different list
        return []
    items = []
    for part in re.split(r",|;|•|\band\b", re.sub(r"\([^)]*\)", "", m.group(2))):
        item = re.sub(r"[\d.]+\s*%|\bat \d+ months\b|>\s*\d+\s*lbs", "", part).strip(" :-–")
        item = re.sub(r"^(asthma|copd|in \w+)\s*:\s*", "", item, flags=re.I).strip()
        if item and len(item.split()) <= 6 and not re.search(r"\b(table|below|placebo|trials?)\b", item, re.I):
            items.append(item[0].upper() + item[1:])
    return items[:10] if len(items) >= 2 else []


def clean(description):
    """'Acute bronchitis (disorder)' -> 'Acute bronchitis'"""
    return description.rsplit(" (", 1)[0] if description.endswith(")") else description


# ---------- cleaned data (shown beside the card; what the questions will read) ----------

_ingredient_cache, _class_cache = {}, {}


def _related_ingredients(rxcui):
    related = fetch_json(f"https://rxnav.nlm.nih.gov/REST/rxcui/{rxcui}/related.json?tty=IN")
    groups = (related or {}).get("relatedGroup", {}).get("conceptGroup") or []
    return [{"rxcui": c["rxcui"], "name": c["name"]} for g in groups for c in g.get("conceptProperties", [])]


def ingredients_for(code, description):
    """RxNorm product -> its active ingredients [{"rxcui", "name"}]; a combination gives several.
    Some Synthea codes are obsolete in RxNorm (e.g. Jolivette 757594), so fall back to the exact name;
    for packs ("{28 (norethindrone 0.35 MG Oral Tablet) } Pack [...]") that's each product inside."""
    key = code or description
    if key not in _ingredient_cache:
        found = _related_ingredients(code) if code else []
        if not found:
            for name in re.findall(r"\d+ \(([^()]+)\)", description) or [description]:
                ids = (fetch_json("https://rxnav.nlm.nih.gov/REST/rxcui.json?name=" + urllib.parse.quote(name))
                       or {}).get("idGroup", {}).get("rxnormId") or []
                found += [i for i in (_related_ingredients(ids[0]) if ids else []) if i not in found]
        _ingredient_cache[key] = [i for i in found if i["name"] != "inert ingredients"]  # a pack's sugar pills
    return _ingredient_cache[key]


# ATC groups for local use (mouth, skin, eyes/ears, nose). Many drugs are also listed there,
# e.g. aspirin and epinephrine both sit in A01AD, which would make them look like "similar drugs".
LOCAL_ATC = ("A01", "D", "S", "R01")


def drug_classes(rxcui):
    """Ingredient -> its ATC classes from RxClass, e.g. [{"id": "J01CE", "name": "Beta-lactamase sensitive penicillins"}]."""
    if rxcui not in _class_cache:
        data = fetch_json(f"https://rxnav.nlm.nih.gov/REST/rxclass/class/byRxcui.json?rxcui={rxcui}&relaSource=ATC")
        infos = (data or {}).get("rxclassDrugInfoList", {}).get("rxclassDrugInfo") or []
        own = [i["rxclassMinConceptItem"] for i in infos if i["minConcept"]["rxcui"] == rxcui]  # not combos it's in
        found = {c["classId"]: c["className"] for c in own if not c["classId"].startswith(LOCAL_ATC)}
        _class_cache[rxcui] = [{"id": k, "name": v} for k, v in sorted(found.items())]
    return _class_cache[rxcui]


def drug_info(ingredients):
    return {"ings": ingredients, "classes": [c for i in ingredients for c in drug_classes(i["rxcui"])]}


def relation(a, b):
    """How two drugs are related: "same drug" (shared ingredient), "same class" (same ATC level-4 class) or None."""
    if {i["rxcui"] for i in a["ings"]} & {i["rxcui"] for i in b["ings"]}:
        return "same drug"
    if {c["id"] for c in a["classes"]} & {c["id"] for c in b["classes"]}:
        return "same class"
    return None


def strength(description):
    """'amiodarone hydrochloride 200 MG Oral Tablet' -> '200 MG'"""
    m = re.search(r"\d[\d.,]*\s*(?:MG|MCG|UNT|MEQ|ML|%)(?:/(?:ML|HR|ACTUAT))?", description)
    return m.group(0) if m else None


def lab_codes_for(reaction):
    d = reaction.lower()
    return [code for words, codes in REACTION_LABS if any(w in d for w in words) for code in codes]


def lab_row(lab, onset):
    name, low, high = LAB_TESTS[lab["code"]]
    abnormal = (low is not None and lab["value"] < low) or (high is not None and lab["value"] > high)
    normal = f"{low}–{high}" if low is not None and high is not None else f"≤ {high}" if high is not None else f"≥ {low}"
    return {"test": name, "date": lab["date"].isoformat(), "day": (lab["date"] - onset).days, "value": lab["value"],
            "units": lab["units"], "normal": normal, "abnormal": abnormal, "planted": lab["planted"]}


def iso(d):
    return d.isoformat() if d else None


def felt_near(onset, pconds, plabs):
    """Symptoms the patient reported or showed near onset: one per kind, the one closest to onset.
    Only what Synthea recorded (or was planted); nothing is inferred from the diagnosis."""
    near = lambda d: FELT_WINDOW[0] <= (d - onset).days <= FELT_WINDOW[1]
    found = {}  # kind -> (days from onset, text, planted)
    for c in pconds:
        d = c["description"].lower()
        if d.endswith("(finding)") and near(c["start"]) and any(w in d for w in FELT_WORDS):
            found[d] = min(found.get(d, (999,)), (abs((c["start"] - onset).days), clean(c["description"]), c["planted"]))
    for l in plabs:
        if l["code"] in FELT_OBS and near(l["date"]):
            show, text = FELT_OBS[l["code"]]
            if show(l["value"]):
                found[l["code"]] = min(found.get(l["code"], (999,)), (abs((l["date"] - onset).days), text(l["value"]), l["planted"]))
    return [{"text": text, "planted": planted} for _, text, planted in sorted(found.values())]


def patient_details(p, onset, group, pconds, pdetails):
    """Who the patient is at onset: demographics, latest check-up readings, and conditions they already had."""
    latest = {}
    for o in sorted(pdetails, key=lambda o: o["date"]):
        if 0 <= (onset - o["date"]).days <= DETAIL_LOOKBACK_DAYS:
            latest[o["key"]] = o["value"]
    bp = f'{float(latest["systolic"]):g}/{float(latest["diastolic"]):g}' if "systolic" in latest and "diastolic" in latest else None
    own = {c["description"] for c in group}
    existing = []
    for c in sorted(pconds, key=lambda c: c["start"]):
        d = c["description"].lower()
        health = d.endswith("(disorder)") or (d.endswith("(finding)") and any(w in d for w in HEALTH_FINDINGS))
        ongoing = c["start"] < onset and (c["stop"] is None or c["stop"] >= onset)
        if health and ongoing and c["description"] not in own and not any(w in d for w in NOT_DRUG_RELATED):
            name = clean(c["description"]).replace("Body mass index 30+ - obesity", "Obesity (BMI 30+)")
            if name not in existing:
                existing.append(name)
    # Synthea leaves earlier stages open ("CKD stage 1, 2, 3" all ongoing): keep only the highest stage
    staged = {}
    for name in existing:
        m = re.match(r"(.*) stage (\d+)$", name)
        if m:
            staged[m.group(1)] = max(staged.get(m.group(1), 0), int(m.group(2)))
    existing = [n for n in existing
                if not (m := re.match(r"(.*) stage (\d+)$", n)) or int(m.group(2)) == staged[m.group(1)]]
    return {
        "race": p["RACE"].capitalize() or None,
        "ethnicity": {"hispanic": "Hispanic", "nonhispanic": "Not Hispanic"}.get(p["ETHNICITY"]),
        "marital": MARITAL.get(p["MARITAL"]),
        "place": p["CITY"] or None,
        "bmi": f'{float(latest["bmi"]):.1f}' if "bmi" in latest else None,
        "blood_pressure": bp,
        "smoking": clean(latest["smoking"]) if "smoking" in latest else None,
        "existing_conditions": existing,
    }


def clean_case(group, onset, drugs_at_onset, pcourses, pconds, plabs, pallergies, labels, info):
    """The cleaned tables for one case, one list of rows per table."""
    reactions = []
    for cond in group:
        d = cond["description"].lower()
        if cond["stop"] is None:
            end_note = "no end date"
        elif any(w in d for w in UNRELIABLE_END):
            end_note = "infection or staged disease: end date says little"
        else:
            end_note = None
        reactions.append({"reaction": clean(cond["description"]), "search_term": clean(cond["description"]).lower(),
                          "code": cond["code"], "start": iso(cond["start"]), "end": iso(cond["stop"]),
                          "end_reliable": end_note is None, "end_note": end_note,
                          "lab_tests": [LAB_TESTS[c][0] for c in lab_codes_for(cond["description"])],
                          "planted": cond["planted"]})

    drug_courses, label_side_effects, re_exposures = [], [], []
    for c in drugs_at_onset:
        i = info[id(c)]
        drug_courses.append({"drug": c["description"],
                             "ingredients": " + ".join(x["name"] for x in i["ings"]) or None,
                             "class": ", ".join(sorted({x["name"] for x in i["classes"]})) or None,
                             "strength": strength(c["description"]), "start": iso(c["start"]), "stop": iso(c["stop"]),
                             "prescriptions_merged": c["rows"]})
        label, via = labels[c["description"]]
        sizes = {k: len(section_text(label, k, limit=None) or "") if label else 0
                 for k in ("boxed_warning", "warnings_and_cautions", "warnings", "adverse_reactions")}
        label_side_effects.append({"drug": c["description"], "found": label is not None, "via": via,
                                   "boxed_warning": sizes["boxed_warning"],
                                   "warnings": sizes["warnings_and_cautions"] or sizes["warnings"],
                                   "adverse_reactions": sizes["adverse_reactions"]})
        for other in pcourses:
            rel = None if other is c else relation(i, info[id(other)])
            if not rel:
                continue
            end = other["stop"] or date.max
            # Did any of this case's reactions also start (on another date) while the other course ran?
            came = [clean(r["description"]) for r in group
                    if any(x["description"] == r["description"] and x["start"] != onset
                           and other["start"] <= x["start"] <= end for x in pconds)]
            re_exposures.append({"drug": c["description"], "other_course": other["description"], "match": rel,
                                 "when": "before" if other["start"] < c["start"] else "after",
                                 "start": iso(other["start"]), "stop": iso(other["stop"]),
                                 "same_reaction_during": came})

    codes = {code for cond in group for code in lab_codes_for(cond["description"])}
    in_window = [l for l in plabs if l["code"] in codes and LAB_WINDOW[0] <= (l["date"] - onset).days <= LAB_WINDOW[1]]
    labs = [lab_row(l, onset) for l in sorted(in_window, key=lambda l: (l["date"], l["code"]))]

    objective_evidence = []
    for cond in group:
        names = {LAB_TESTS[c][0] for c in lab_codes_for(cond["description"])}
        hits = [l for l in labs if l["test"] in names and l["abnormal"]
                and EVIDENCE_WINDOW[0] <= l["day"] <= EVIDENCE_WINDOW[1]]
        objective_evidence.append({"reaction": clean(cond["description"]),
                                   "found": bool(hits),
                                   "evidence": [f'{h["test"]} {h["value"]:g} {h["units"]} on day {h["day"]} (normal {h["normal"]})'
                                                for h in hits],
                                   "note": None if names else "no lab test measures this reaction"})

    drug_allergies = []
    for a in pallergies:
        allergen = drug_info([{"rxcui": a["CODE"], "name": a["DESCRIPTION"]}])
        drug_allergies.append({"allergen": a["DESCRIPTION"], "type": a["TYPE"],
                               "reaction": clean(a["DESCRIPTION1"]) if a["DESCRIPTION1"] else None,
                               "severity": a["SEVERITY1"].lower() or None, "since": iso(parse_date(a["START"])),
                               "class": ", ".join(x["name"] for x in allergen["classes"]) or None,
                               "matches": [{"drug": c["description"], "match": rel} for c in drugs_at_onset
                                           if (rel := relation(allergen, info[id(c)]))]})

    return {"reactions": reactions, "drug_courses": drug_courses, "label_side_effects": label_side_effects,
            "labs": labs, "objective_evidence": objective_evidence, "re_exposures": re_exposures,
            "drug_allergies": drug_allergies}


# ---------- questions ----------
# Each check(ctx) returns (answer, why): answer is "yes" / "no" / "unknown" and why quotes the evidence used.
# "unknown" always scores 0. ctx: course, condition, onset, reaction (its cleaned row), label, info (drug info
# by id(course)), pcourses, pconds, plabs, pallergies.

AFTER_ONSET_DAYS = 30   # a drug started this soon after onset is still listed, as a likely treatment (Q2: −1)
STOP_HELPED_DAYS = 60   # Q3: the reaction must clear within this long after stopping
RECUR_DAYS = 90         # Q4: the reaction must come back within this long after restarting

SIDE_EFFECT_SECTIONS = [("boxed_warning", "Boxed warning"), ("warnings_and_cautions", "Warnings and precautions"),
                        ("warnings", "Warnings"), ("adverse_reactions", "Adverse reactions")]
# Label wording that means the reaction itself happened as a side effect (exact phrases only).
# Reactions not listed here are searched by their own name.
LABEL_TERMS = {
    "hepatic enzyme increased": ["hepatic enzyme", "liver enzyme", "hepatic injury", "liver injury", "hepatotoxicity",
                                 "alt increased", "elevated alt", "transaminase"],
    "anemia": ["anemia"],
    "diabetes mellitus type 2": ["diabetes mellitus", "new-onset diabetes", "hyperglycemia"],
    "hypertriglyceridemia": ["hypertriglyceridemia", "increased triglycerides", "elevated triglycerides",
                             "triglycerides increased"],
    "chronic kidney disease stage 4": ["renal failure", "kidney failure", "nephrotoxicity", "acute kidney injury"],
    "end-stage renal disease": ["renal failure", "kidney failure", "nephrotoxicity", "acute kidney injury"],
    "acute bacterial sinusitis": ["sinusitis"],
    "chronic sinusitis": ["sinusitis"],
    "viral sinusitis": ["sinusitis"],
    "acute viral pharyngitis": ["pharyngitis"],
    "streptococcal sore throat": ["pharyngitis", "sore throat"],
    "metabolic syndrome x": ["metabolic syndrome"],
    "non-small cell carcinoma of lung  tnm stage 1": ["lung cancer", "carcinoma of the lung"],
}
# Text just before a match that means the label is describing who takes the drug, not a side effect
# ("...for non-small cell lung cancer", "If sore throat is severe...")
POPULATION = re.compile(r"\b(patients with|history of|treatment of|to treat|indicated for|due to|caused by|for|if)"
                        r"\W+(\w+\W+){0,3}$")
# Sentences that only say to test for something ("Obtain baseline and periodic liver transaminases"),
# or describe harm to an unborn or newborn child rather than the patient
MONITORING = re.compile(r"\b(monitor|obtain|baseline|measure|check)\w*")
NOT_THE_PATIENT = re.compile(r"\b(neonat|fetus|fetal|newborn|pregnan|infant)\w*")


def days_text(n):
    n = abs(n)
    if n < 14:
        return f"{n} day{'s' if n != 1 else ''}"
    if n < 120:
        return f"{round(n / 7)} weeks"
    if n < 730:
        return f"{round(n / 30)} months"
    return f"{round(n / 365)} years"


def dt(d):
    """2022-03-01 -> 1 Mar 2022"""
    return f"{d.day} {d.strftime('%b %Y')}"


def short(description):
    return clean(description).split(" [")[0]


def reaction_is_episodic(cond):
    """Infections and staged diseases: their end and recurrence say little about a drug."""
    return any(w in cond["description"].lower() for w in UNRELIABLE_END)


def q1_known(ctx):
    label = ctx["label"]
    if label is None:
        return "unknown", "No openFDA label was found for this drug, so it can't be checked."
    reaction = clean(ctx["condition"]["description"]).lower()
    terms = LABEL_TERMS.get(reaction, [reaction])
    # A drug used for this condition mentions it all over its label (paclitaxel and lung cancer)
    uses = (section_text(label, "indications_and_usage", limit=None) or "").lower()
    treats = next((t for t in terms if re.search(r"\b" + re.escape(t), uses)), None)
    if treats:
        return "unknown", (f'The label\'s "Indications and usage" mentions {treats}, so other mentions may be about '
                           f'what the drug is used for rather than a side effect.')
    # Terms in priority order; within a term, sections in order of seriousness
    sections = [(title, re.split(r"(?<=[.;])\s+", " ".join((section_text(label, key, limit=None) or "").split())))
                for key, title in SIDE_EFFECT_SECTIONS]
    for term in terms:
        for title, sentences in sections:
            for sentence in sentences:
                low = sentence.lower()
                hits = [m.start() for m in re.finditer(r"\b" + re.escape(term), low)]
                # Skip the sentence if any mention is a condition ("If sore throat is severe")
                if hits and not (any(POPULATION.search(low[:h]) for h in hits)
                                 or MONITORING.search(low) or NOT_THE_PATIENT.search(low)):
                    return "yes", f'Its label ({title.lower()}): "{snippet(sentence, term)}"'
    return "no", f"Not in the label's boxed warning, warnings or adverse reactions (searched: {', '.join(terms)})."


def q2_timing(ctx):
    start, onset = ctx["course"]["start"], ctx["onset"]
    gap = (onset - start).days
    if gap > 0:
        return "yes", f"Started {dt(start)}, {days_text(gap)} before the reaction began ({dt(onset)})."
    if gap == 0:
        return "no", f"Started the same day the reaction was recorded ({dt(onset)}), so it didn't come first."
    return "no", f"Started {dt(start)}, {days_text(gap)} after the reaction began ({dt(onset)})."


def first_normal_after(ctx, after):
    """Q3 lab check: for a test that was abnormal near onset, the first normal result after `after`."""
    codes = lab_codes_for(ctx["condition"]["description"])
    onset = ctx["onset"]
    rows = sorted((l for l in ctx["plabs"] if l["code"] in codes and (l["date"] - onset).days >= EVIDENCE_WINDOW[0]),
                  key=lambda l: l["date"])
    for code in codes:
        r = [lab_row(l, onset) | {"raw": l} for l in rows if l["code"] == code]
        high = [x for x in r if x["abnormal"] and x["day"] <= EVIDENCE_WINDOW[1]]
        later = [x for x in r if not x["abnormal"] and x["raw"]["date"] >= after]
        if high and later:
            return high[0], later[0]
    return None


def q3_dechallenge(ctx):
    c, cond = ctx["course"], ctx["condition"]
    if c["start"] >= ctx["onset"]:
        return "unknown", "Started after the reaction began, so stopping it can't show anything."
    if reaction_is_episodic(cond):
        return "unknown", "Infection or staged disease: its end date says little about stopping a drug."
    if c["stop"] is None:
        return "unknown", "The drug was never stopped, so there's no way to see whether stopping helped."
    labs = first_normal_after(ctx, c["stop"])
    if labs:
        high, normal = labs
        gap = (normal["raw"]["date"] - c["stop"]).days
        text = (f"Stopped {dt(c['stop'])}; {high['test']} went from {high['value']:g} to {normal['value']:g} "
                f"{normal['units']} (normal {normal['normal']}) by {dt(parse_date(normal['date']))}, {days_text(gap)} later.")
        return ("yes", text) if gap <= STOP_HELPED_DAYS else ("no", text + f" Longer than {STOP_HELPED_DAYS} days.")
    if cond["stop"] is None:
        return "unknown", f"Stopped {dt(c['stop'])}, but the reaction has no end date."
    if c["stop"] > cond["stop"]:
        return "no", f"The reaction ended ({dt(cond['stop'])}) while the drug was still being taken (stopped {dt(c['stop'])})."
    gap = (cond["stop"] - c["stop"]).days
    if gap <= STOP_HELPED_DAYS:
        return "yes", f"Stopped {dt(c['stop'])}; the reaction ended {dt(cond['stop'])}, {days_text(gap)} later."
    return "no", f"Stopped {dt(c['stop'])}; the reaction only ended {dt(cond['stop'])}, {days_text(gap)} later."


def q4_rechallenge(ctx):
    c, cond = ctx["course"], ctx["condition"]
    if c["start"] >= ctx["onset"]:
        return "unknown", "Started after the reaction began, so a restart can't show anything."
    if reaction_is_episodic(cond):
        return "unknown", "Infection or staged disease: a return wouldn't point to the drug."
    if cond["stop"] is None:
        return "unknown", "The reaction never ended, so it can't 'come back'."
    me = ctx["info"][id(c)]
    restarts = sorted((o for o in ctx["pcourses"] if o is not c and o["start"] > cond["stop"]
                       and relation(me, ctx["info"][id(o)]) == "same drug"), key=lambda o: o["start"])
    if not restarts:
        return "unknown", f"Not given again after the reaction ended ({dt(cond['stop'])})."
    r = restarts[0]
    back = [x for x in ctx["pconds"] if x["description"] == cond["description"]
            and r["start"] <= x["start"] <= r["start"] + timedelta(days=RECUR_DAYS)]
    if back:
        return "yes", f"Restarted {dt(r['start'])} ({short(r['description'])}); the reaction began again {dt(back[0]['start'])}."
    return "no", f"Restarted {dt(r['start'])} ({short(r['description'])}); the reaction did not return within {RECUR_DAYS} days."


def similar_reaction(a, b):
    a, b = clean(a).lower(), clean(b).lower()
    return a == b or bool(set(LABEL_TERMS.get(a, [a])) & set(LABEL_TERMS.get(b, [b])))


def q8_previous(ctx):
    c, cond, onset = ctx["course"], ctx["condition"], ctx["onset"]
    me = ctx["info"][id(c)]
    notes = []
    for a in ctx["pallergies"]:
        rel = relation(drug_info([{"rxcui": a["CODE"], "name": a["DESCRIPTION"]}]), me)
        if not rel:
            continue
        if a["DESCRIPTION1"] and similar_reaction(a["DESCRIPTION1"], cond["description"]):
            return "yes", f"Allergy to {a['DESCRIPTION']} ({rel}) on record with {clean(a['DESCRIPTION1']).lower()}."
        notes.append(f"allergy to {a['DESCRIPTION']} ({rel}) is on record, but with "
                     + (f"a different reaction ({clean(a['DESCRIPTION1']).lower()})" if a["DESCRIPTION1"] else "no reaction listed"))
    earlier = [o for o in ctx["pcourses"] if o is not c and o["start"] < c["start"] and relation(me, ctx["info"][id(o)])]
    if earlier and not reaction_is_episodic(cond):
        for o in earlier:
            end = min(o["stop"] or onset, onset)
            past = [x for x in ctx["pconds"] if x["description"] == cond["description"] and o["start"] <= x["start"] < end]
            if past:
                return "yes", (f"The same reaction began {dt(past[0]['start'])} during an earlier course of "
                               f"{short(o['description'])} ({relation(me, ctx['info'][id(o)])}).")
        notes.append(f"{len(earlier)} earlier course(s) of this or a similar drug, none with this reaction")
    if notes:
        return "no", "No similar reaction before: " + "; ".join(notes) + "."
    if earlier:
        return "unknown", "Taken before, but an infection or staged disease coming back again wouldn't point to the drug."
    return "unknown", "No earlier course of this or a similar drug, and no drug allergy on record."


def q10_objective(ctx):
    cond, onset = ctx["condition"], ctx["onset"]
    codes = lab_codes_for(cond["description"])
    if not codes:
        return "unknown", "No lab test measures this reaction in this data."
    window = [lab_row(l, onset) for l in ctx["plabs"]
              if l["code"] in codes and EVIDENCE_WINDOW[0] <= (l["date"] - onset).days <= EVIDENCE_WINDOW[1]]
    hits = [r for r in window if r["abnormal"]]
    if hits:
        h = max(hits, key=lambda r: r["value"])
        return "yes", f"{h['test']} {h['value']:g} {h['units']} on {dt(parse_date(h['date']))} (normal {h['normal']})."
    names = ", ".join(sorted({LAB_TESTS[c][0] for c in codes}))
    if window:
        return "no", f"{names} tested near onset and normal ({len(window)} result{'s' if len(window) != 1 else ''})."
    return "unknown", f"No {names} test between {-EVIDENCE_WINDOW[0]} days before and {EVIDENCE_WINDOW[1]} days after onset."


# (number, question, short name, points for yes, points for no, check). Naranjo Q5–Q7 were dropped: no data.
QUESTIONS = [
    (1, "Are there previous conclusive reports on this reaction?", "Known side effect", 1, 0, q1_known),
    (2, "Did the adverse event appear after the suspected drug was given?", "Started after the drug", 2, -1, q2_timing),
    (3, "Did the reaction improve when the drug was discontinued?", "Better after stopping", 1, 0, q3_dechallenge),
    (4, "Did the reaction reappear when the drug was given again?", "Back after restarting", 2, -1, q4_rechallenge),
    (8, "Did the patient have a similar reaction to the same or a similar drug before?", "Similar reaction before", 1, 0, q8_previous),
    (10, "Was the adverse event confirmed by objective evidence?", "Objective evidence", 1, 0, q10_objective),
]


def answer_questions(ctx):
    answers, score = [], 0
    for number, question, name, yes, no, check in QUESTIONS:
        answer, why = check(ctx)
        points = yes if answer == "yes" else no if answer == "no" else 0
        score += points
        answers.append({"number": number, "question": question, "short": name, "answer": answer,
                        "points": points, "why": why})
    return answers, score


# ---------- assembling cases ----------

def is_candidate_condition(c):
    d = c["description"].lower()
    if c.get("symptom"):  # planted symptoms go with a planted reaction; they aren't a case of their own
        return False
    return (c["planted"] or (d.endswith("(disorder)") and is_clinical(d)
                             and not any(w in d for w in NOT_DRUG_RELATED)))


def role(course, onset):
    gap = (onset - course["start"]).days
    return "After" if gap <= 0 else "New" if gap <= RECENT_DAYS else "Ongoing"


def drug_entry(course, condition, labels, patient):
    """One drug for one symptom: its answers to QUESTIONS and the total score."""
    ctx = {"course": course, "condition": condition, "onset": condition["start"],
           "label": labels[course["description"]][0], **patient}
    answers, score = answer_questions(ctx)
    return {"name": course["description"], "role": role(course, condition["start"]),
            "answers": answers, "score": score}


def build_cases():
    patients, courses, conds, labs, allergies, details = load_patients()
    cases = []
    for pid, p in patients.items():
        pcourses, pconds = courses.get(pid, []), conds.get(pid, [])
        plabs, pallergies = labs.get(pid, []), allergies.get(pid, [])
        info = {id(c): drug_info(ingredients_for(c["code"], c["description"])) for c in pcourses}
        patient = {"info": info, "pcourses": pcourses, "pconds": pconds, "plabs": plabs, "pallergies": pallergies}
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
            # Drugs started on or just after onset are listed too: Q2 marks them down as likely treatments
            after = [c for c in pcourses if 0 <= (c["start"] - onset).days <= AFTER_ONSET_DAYS]
            # One entry per drug: the course that was running at onset
            seen, drugs_at_onset = set(), []
            for c in sorted(active, key=lambda c: c["start"], reverse=True) + sorted(after, key=lambda c: c["start"]):
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
                    "drugs": [drug_entry(c, cond, labels, patient) for c in drugs_at_onset],
                })

            drugs = []
            for c in drugs_at_onset:
                label, via = labels[c["description"]]
                entry = {"name": c["description"], "role": role(c, onset),
                         "indication": clean(c["reason"]) if c["reason"] else None,
                         "label_found": label is not None, "label_via": via,
                         "started": c["start"].isoformat(), "stopped": c["stop"].isoformat() if c["stop"] else None}
                if label:
                    entry["boxed_headline"] = boxed_headline(label)
                    entry["serious_side_effects"] = serious_side_effects(label)
                    entry["common_side_effects"] = common_side_effects(label)
                    entry["boxed_warning"] = section_text(label, "boxed_warning")
                    entry["warnings"] = section_text(label, "warnings_and_cautions") or section_text(label, "warnings")
                    entry["adverse_reactions"] = section_text(label, "adverse_reactions")
                drugs.append(entry)

            birth = parse_date(p["BIRTHDATE"])
            age = onset.year - birth.year - ((onset.month, onset.day) < (birth.month, birth.day))
            cases.append({
                "id": f"{pid[:8]}-{onset.isoformat()}",
                "person_id": pid,
                "name": display_name(p),
                "age": str(age),
                "sex": SEX.get(p["GENDER"], "Unknown"),
                "onset": onset.isoformat(),
                "reactions": [clean(c["description"]) for c in group],
                "felt": felt_near(onset, pconds, plabs),
                "details": patient_details(p, onset, group, pconds, details.get(pid, [])),
                "drugs": drugs,
                "assessment": assessment,
                "cleaned": clean_case(group, onset, drugs_at_onset, pcourses, pconds, plabs, pallergies, labels, info),
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
