"""Run:  python -m pytest analytics -q"""
from datetime import date, timedelta

import pytest

from analytics.loaders import Patient, from_trial_rows
from analytics.model import Signals, build, prr_stats
from analytics.normalize import condition_name, drug_names


def test_drug_names():
    assert drug_names("24 HR Metformin hydrochloride 500 MG Extended Release Oral Tablet") == ["metformin"]
    assert drug_names("Acetaminophen 325 MG / Oxycodone Hydrochloride 10 MG Oral Tablet [Percocet]") == ["acetaminophen", "oxycodone"]
    assert drug_names("{28 (norethindrone 0.35 MG Oral Tablet) } Pack [Errin]") == ["norethindrone"]
    assert drug_names("NDA020800 0.3 ML Epinephrine 1 MG/ML Auto-Injector") == ["epinephrine"]
    assert drug_names("1 ML medroxyPROGESTERone acetate 150 MG/ML Injection") == ["medroxyprogesterone acetate"]
    assert drug_names("") == []


def test_condition_names_drop_social_entries():
    assert condition_name("Essential hypertension (disorder)") == "Essential hypertension"
    assert condition_name("Chronic pain (finding)") == "Chronic pain"
    assert condition_name("Full-time employment (finding)") is None
    assert condition_name("Medication review due (situation)") is None
    assert condition_name("Educated to high school level (finding)") is None


def test_prr_matches_hand_calculation():
    prr, low, chi2 = prr_stats(10, 90, 5, 895)  # 10% on drug vs 0.56% off drug
    assert prr == pytest.approx(0.1 / (5 / 900))
    assert 1 < low < prr
    assert chi2 > 4


def _patient(pid, drugs=(), conds=(), start=None, onset=None, reasons=()):
    p = Patient(id=pid)
    for d in drugs:
        p.drugs[d] = (start, None)
    for c in conds:
        p.conditions[c] = onset
    p.indications = set(reasons)
    return p


def test_signal_found_and_indication_and_timing_respected():
    d0 = date(2020, 1, 1)
    pop = []
    # 8 people on "testdrug" get "rash" 10 days later; 2 of them took it FOR rash (not reactions)
    for i in range(8):
        reasons = {("testdrug", "Rash")} if i < 2 else set()
        pop.append(_patient(f"a{i}", ["testdrug"], ["Rash"], d0, d0 + timedelta(days=10), reasons))
    # 4 people on testdrug whose rash came BEFORE the drug: must not count
    for i in range(4):
        pop.append(_patient(f"b{i}", ["testdrug"], ["Rash"], d0, d0 - timedelta(days=30)))
    # 40 people not on it, 1 with rash
    pop += [_patient(f"c{i}", ["other"], ["Rash"] if i == 0 else ["Cold"], d0, d0) for i in range(40)]

    s = Signals(pop, window_days=90, min_n=3).pair("testdrug", "Rash")
    assert s["n"] == 6 and s["exposed"] == 12 and s["dated"] == 6 and s["treats"] == 2
    assert s["signal"] is True


def test_build_places_cases_and_handles_tiny_data():
    pop = [_patient(f"p{i}", ["metformin", "lisinopril"] if i % 2 else ["aspirin"],
                    ["Diabetes mellitus type 2"] if i % 2 else ["Headache"]) for i in range(12)]
    out = build(pop, k=2)
    assert out["counts"]["patients"] == 12
    assert {p["cluster"] for p in out["points"]} == {0, 1}
    assert out["graph"]["nodes"]
    tiny = build(pop[:2])
    assert tiny["params"]["clusters"] == 1


def test_trial_rows_accept_json_and_postgres_arrays():
    rows = [
        {"patient_id": "x", "trial_name": "T1", "all_medications": '["lisinopril 10 MG Oral Tablet"]',
         "adverse_events": '["Essential hypertension (disorder)", "Stress (finding)"]'},
        {"patient_id": "y", "trial_name": "T1", "all_medications": '{"Simvastatin 10 MG Oral Tablet"}',
         "adverse_events": "{Hyperlipidemia (disorder)}"},
    ]
    a, b = from_trial_rows(rows)
    assert list(a.drugs) == ["lisinopril"] and list(a.conditions) == ["Essential hypertension"]
    assert list(b.drugs) == ["simvastatin"] and list(b.conditions) == ["Hyperlipidemia"]
