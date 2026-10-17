import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request

NUM_REPORTS = 10
MAX_TEXT = 1500  # cap label text shown on the page so the data file stays small
SEX = {"1": "Male", "2": "Female"}

# Label sections searched for a reaction, most serious first
LABEL_SECTIONS = [
    ("boxed_warning", "Boxed warning"),
    ("warnings_and_cautions", "Warnings and precautions"),
    ("warnings", "Warnings"),
    ("precautions", "Precautions"),
    ("adverse_reactions", "Adverse reactions"),
    # Over-the-counter labels have no adverse_reactions section; side effects live here
    ("stop_use", "Stop use and ask a doctor if"),
    ("ask_doctor", "Ask a doctor before use if"),
    ("when_using", "When using this product"),
]

# MedDRA terms (used in FAERS) often differ from label wording. Keys are
# lowercase reaction terms; values are extra phrases to look for in the label.
SYNONYMS = {
    "hepatic enzyme increased": ["aminotransferase", "transaminase", "liver enzyme", "alt elevation"],
    "dyspepsia": ["heartburn", "indigestion", "stomach upset"],
    "renal impairment": ["kidney problem", "kidney disease", "renal failure", "renal function"],
    "rhinorrhoea": ["runny nose", "nasal congestion", "rhinitis"],
    "drug hypersensitivity": ["hypersensitivity", "allergic reaction"],
}

# FAERS codes (openFDA event API docs)
ACTION = {"1": "withdrawn", "2": "dose reduced", "3": "dose increased",
          "4": "dose not changed", "5": "unknown", "6": "not applicable"}
RECOVERED = {"1", "2"}  # reactionoutcome: recovered / recovering

# Reaction terms that describe a use problem, not a clinical event to explain
NOT_CLINICAL = ["ineffective", "off label", "overdose", "error", "misuse",
                "unevaluable", "no adverse event", "product use", "abuse"]


def fetch_json(url):
    """GET a URL and parse JSON. Returns None on 404 (no match), retries on rate limit."""
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url) as response:
                return json.load(response)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            if e.code == 429 or e.code >= 500:
                time.sleep(2 * (attempt + 1))
                continue
            raise
    print("  (giving up on", url[:90], ")")
    return None


def name_variants(name):
    name = name.split("/")[0].strip()   # "AVOLVE / DUTASTERIDE" -> "AVOLVE"
    base = name.split("-")[0].strip()   # "DURAGESIC-100" -> "DURAGESIC"
    first = base.split()[0]             # first word only
    return list(dict.fromkeys([name, base, first]))


_label_cache = {}


def search_label(name):
    for variant in name_variants(name):
        for field in ["openfda.brand_name", "openfda.generic_name"]:
            query = f'{field}:"{variant}"'
            url = ("https://api.fda.gov/drug/label.json?search="
                   + urllib.parse.quote_plus(query) + "&limit=1")
            data = fetch_json(url)
            if data and data.get("results"):
                return data["results"][0]
    return None


def rxnorm_ingredients(name):
    """Ingredient names for a brand, from RxNorm (NLM, free, no key).
    Uses exact-name lookup only: fuzzy matching returned wrong drugs in testing
    (e.g. "DURAGESIC" -> a calamine cream called Dermagesic)."""
    for variant in name_variants(name):
        data = fetch_json("https://rxnav.nlm.nih.gov/REST/drugs.json?name=" + urllib.parse.quote(variant))
        groups = (data or {}).get("drugGroup", {}).get("conceptGroup") or []
        products = [c for g in groups for c in g.get("conceptProperties", [])]
        if not products:
            continue
        related = fetch_json(f"https://rxnav.nlm.nih.gov/REST/rxcui/{products[0]['rxcui']}/related.json?tty=IN")
        groups = (related or {}).get("relatedGroup", {}).get("conceptGroup") or []
        ingredients = [c["name"] for g in groups for c in g.get("conceptProperties", [])]
        if ingredients:
            return ingredients
    return []


def cached_search(name):
    if name not in _label_cache:
        _label_cache[name] = search_label(name)
    return _label_cache[name]


def get_label(name, fallback_names=()):
    """Returns (label, how it was found). Tries the reported name, then the generic
    names in the report, then the ingredients RxNorm lists for the brand."""
    for candidate in [name, *fallback_names]:
        label = cached_search(candidate)
        if label:
            return label, (None if candidate == name else f"generic name {candidate.lower()}")
    for ingredient in rxnorm_ingredients(name):
        label = cached_search(ingredient)
        if label:
            return label, f"ingredient {ingredient}, via RxNorm"
    return None, None


def section_text(label, key, limit=MAX_TEXT):
    value = label.get(key)
    if not value:
        return None
    text = " ".join(value)
    return text[:limit] if limit else text


# ---------- matching a reaction term against label text ----------

def normalize(text):
    # FAERS uses British MedDRA spellings ("Diarrhoea"); labels use US ones.
    # Applying the same rewrite to both sides keeps the comparison consistent.
    text = text.lower().replace("oe", "e").replace("ae", "e")
    return re.sub(r"[^a-z0-9 ]+", " ", text)


def find_in_label(label, reaction):
    """Return (section title, quoted sentence) for the first label mention, or None.
    Tries the reaction term itself, then any synonyms for it."""
    for term in [reaction, *SYNONYMS.get(reaction.lower(), [])]:
        hit = find_term(label, term)
        if hit:
            return hit
    return None


def find_term(label, reaction):
    term = normalize(reaction).split()
    words = [w for w in term if len(w) > 3] or term
    phrase = " ".join(term)
    for key, title in LABEL_SECTIONS:
        text = section_text(label, key, limit=None)
        if not text:
            continue
        sentences = re.split(r"(?<=[.;])\s+", text)
        # Exact phrase anywhere beats all-words-in-one-sentence
        for match_all_words in (False, True):
            for s in sentences:
                ns = " " + normalize(s) + " "
                hit = (all(w in ns for w in words) if match_all_words
                       else f" {phrase} " in ns)
                if hit:
                    return title, snippet(s, words[0])
    return None


def snippet(sentence, word, radius=150):
    """Quote the text around the matched word (OTC labels have few full stops)."""
    s = " ".join(sentence.split())
    pos = max(s.lower().find(word), 0)
    start, end = max(pos - radius, 0), min(pos + radius, len(s))
    return ("…" if start else "") + s[start:end] + ("…" if end < len(s) else "")


def is_clinical(reaction):
    r = reaction.lower()
    return not any(word in r for word in NOT_CLINICAL)


# ---------- building reasons for / against each drug ----------

def reasons_for_drug(drug, reaction, outcome, labels, all_drugs):
    label = labels.get(drug["name"])
    raw = drug["_raw"]
    for_, against, unknown = [], [], []

    # Previous reports / known reaction (Naranjo Q1)
    if label is None:
        unknown.append({"text": "No label found, so it can't be checked whether this reaction is known for this drug."})
    else:
        hit = find_in_label(label, reaction)
        if hit:
            section, quote = hit
            serious = " (the label's most serious warning)" if section == "Boxed warning" else ""
            via = f" (found by {drug['label_via']})" if drug.get("label_via") else ""
            for_.append({"text": f"The label{via} lists this reaction under {section}{serious}.",
                         "section": section, "quote": quote})
        else:
            against.append({"text": "The reaction is not mentioned in the label sections checked."})

    # How the reporter classed the drug
    if drug["role"] == "Suspect":
        for_.append({"text": "The reporter marked this drug as a suspect."})
    else:
        against.append({"text": "The reporter listed this drug as concomitant, not suspect."})

    # Alternate causes (Naranjo Q5): other drugs whose labels mention the reaction
    others = [d["name"] for d in all_drugs
              if d["name"] != drug["name"] and labels.get(d["name"])
              and find_in_label(labels[d["name"]], reaction)]
    if others:
        against.append({"text": "Other drugs in this report also list this reaction: "
                        + ", ".join(others) + "."})

    # Dechallenge (Naranjo Q3)
    action = raw.get("actiondrug")
    if action == "1" and outcome in RECOVERED:
        for_.append({"text": "The reaction improved after this drug was stopped."})
    elif action == "4" and outcome in RECOVERED:
        against.append({"text": "The reaction improved even though this drug was continued at the same dose."})
    else:
        unknown.append({"text": "What happened when the drug was stopped is "
                        + (f"not useful here (drug {ACTION[action]})." if action in ACTION
                           else "not reported.")})

    # Rechallenge (Naranjo Q4)
    recur = raw.get("drugrecurreadministration")
    if recur == "1":
        for_.append({"text": "The reaction came back when the drug was given again."})
    elif recur == "2":
        against.append({"text": "The reaction did not come back when the drug was given again."})
    else:
        unknown.append({"text": "Whether the reaction came back on re-exposure is not reported."})

    # Timing (Naranjo Q2): openFDA has no reaction start date to compare against
    unknown.append({"text": "Timing can't be checked: the report has no reaction start date"
                    + (f" (drug started {raw['drugstartdate']})." if raw.get("drugstartdate") else ".")})

    return {"name": drug["name"], "role": drug["role"],
            "for": for_, "against": against, "unknown": unknown}


def build_assessment(patient_raw, drugs, labels):
    assessment = []
    for r in patient_raw.get("reaction", []):
        reaction = r["reactionmeddrapt"]
        if not is_clinical(reaction):
            assessment.append({"reaction": reaction, "assessable": False,
                               "note": "Describes how the drug was used, not a clinical reaction, so no cause is suggested."})
            continue
        assessment.append({
            "reaction": reaction,
            "assessable": True,
            "drugs": [reasons_for_drug(d, reaction, r.get("reactionoutcome"), labels, drugs)
                      for d in drugs],
        })
    return assessment


# ---------- assembling the page data ----------

def build_drug(drug, label):
    entry = {
        "name": drug.get("medicinalproduct") or "UNKNOWN",
        "role": "Suspect" if drug.get("drugcharacterization") == "1" else "Concomitant",
        "indication": drug.get("drugindication"),
        "label_found": label is not None,
    }
    if label:
        entry["boxed_warning"] = section_text(label, "boxed_warning")
        entry["warnings"] = section_text(label, "warnings_and_cautions") or section_text(label, "warnings")
        entry["adverse_reactions"] = section_text(label, "adverse_reactions")
    return entry


def build_patient(report):
    patient = report["patient"]

    # Reports often list the same drug twice (e.g. once per indication); keep one
    drugs, labels = [], {}
    for raw in patient.get("drug", []):
        name = raw.get("medicinalproduct") or "UNKNOWN"
        if name in labels:
            continue
        labels[name], via = get_label(name, raw.get("openfda", {}).get("generic_name", []))
        entry = build_drug(raw, labels[name])
        entry["label_via"] = via
        entry["_raw"] = raw
        drugs.append(entry)

    assessment = build_assessment(patient, drugs, labels)
    for d in drugs:
        del d["_raw"]

    return {
        "id": report["safetyreportid"],
        "age": patient.get("patientonsetage"),
        "sex": SEX.get(patient.get("patientsex"), "Unknown"),
        "reactions": [r["reactionmeddrapt"] for r in patient.get("reaction", [])],
        "drugs": drugs,
        "assessment": assessment,
    }


def main():
    url = f"https://api.fda.gov/drug/event.json?limit={NUM_REPORTS}"
    reports = fetch_json(url)["results"]

    patients = []
    for report in reports:
        p = build_patient(report)
        print(f"Report {p['id']}: {len(p['drugs'])} drugs")
        patients.append(p)

    # Written as a .js file so index.html works by double-clicking (no server needed)
    with open("data.js", "w") as f:
        f.write("const PATIENTS = " + json.dumps(patients, indent=2) + ";\n")

    # FAERS copy for reference; the React app now loads data.json, written by synthea_pipeline.py
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "frontend", "public", "faers.json")
    with open(out, "w") as f:
        json.dump(patients, f, indent=2)
    print(f"Saved {len(patients)} patients to data.js and frontend/public/faers.json")


if __name__ == "__main__":
    main()
