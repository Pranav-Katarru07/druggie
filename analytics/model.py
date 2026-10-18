"""Population insights for the swipe app: clusters, signals, knowledge graph, triage order.

The swipe deck holds a handful of cases. This module looks at the WHOLE population the cases come
from (every Synthea patient, or every trial participant) and answers, for each card:
  - Which group of similar patients is this person in?          (PCA + k-means clustering)
  - Across the population, do people on this drug get this       (disproportionality: PRR with the
    condition more often than people not on it?                   Evans criteria used in pharmacovigilance)
  - Which other cases look like this one?                        (cosine similarity)
  - Which cards should a doctor swipe first?                     (priority score)
It also builds a knowledge graph of drugs and conditions for the Insights page.

Rules that keep the signals honest:
  - Conditions a drug was prescribed FOR (Synthea REASONDESCRIPTION) never count as reactions.
  - With dates, a condition only counts if it began 0..window_days after the drug started.
  - Social and admin entries ("Full-time employment") are dropped in normalize.py.
None of this proves a drug caused anything. It decides what to look at first.
"""
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone

import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score

from .loaders import Case, Patient

CAVEATS = [
    "Signals show a drug and a condition appearing together more often than expected. They do not show cause.",
    "Conditions a drug was prescribed for are excluded when the data records the reason.",
    "Without dates, any condition the patient ever had counts, so confounding is likely.",
    "Synthea is synthetic: its drugs never cause conditions, so signals there come from how it simulates care.",
]


# ---------------------------------------------------------------- features, PCA, clusters

class Embedding:
    """Patients -> IDF-weighted yes/no features -> PCA. Can place new patients (cases) on the same map."""

    def __init__(self, patients: list[Patient], min_support: int, seed: int):
        df = Counter()
        for p in patients:
            df.update(self._keys(p))
        self.names = sorted(f for f, n in df.items() if n >= min_support)
        if not self.names:
            raise ValueError("No drug or condition is shared by enough patients. Lower --min-support.")
        self.index = {f: i for i, f in enumerate(self.names)}
        X = self.binary(patients)
        n = len(patients)
        self.idf = np.log((1 + n) / (1 + X.sum(axis=0))) + 1.0
        self.X = X
        self.W = self.weight(X)
        dims = max(1, min(2, n - 1, len(self.names)))
        self.map = PCA(n_components=dims, random_state=seed).fit(self.W)
        zdims = max(1, min(10, n - 1, len(self.names)))
        self.space = PCA(n_components=zdims, random_state=seed).fit(self.W) if n > 1 else None

    @staticmethod
    def _keys(p: Patient):
        return [f"drug:{d}" for d in p.drugs] + [f"cond:{c}" for c in p.conditions]

    def binary(self, patients):
        X = np.zeros((len(patients), len(self.names)))
        for r, p in enumerate(patients):
            for f in self._keys(p):
                j = self.index.get(f)
                if j is not None:
                    X[r, j] = 1.0
        return X

    def weight(self, X):
        W = X * self.idf
        norms = np.linalg.norm(W, axis=1, keepdims=True)
        return np.divide(W, norms, out=np.zeros_like(W), where=norms > 0)

    def xy(self, W):
        out = self.map.transform(W)
        return np.hstack([out, np.zeros((len(W), 1))]) if out.shape[1] == 1 else out

    def z(self, W):
        return self.space.transform(W) if self.space is not None else W

    def axes(self):
        result = []
        for i, load in enumerate(self.map.components_):
            order = np.argsort(-np.abs(load))[:6]
            result.append({
                "explained": round(float(self.map.explained_variance_ratio_[i]), 3),
                "top": [{"feature": self.names[j].split(":", 1)[1], "kind": self.names[j].split(":")[0],
                         "weight": round(float(load[j]), 3)} for j in order],
            })
        return result


def _choose_k(Z, seed, k):
    n = len(Z)
    if k:
        return max(1, min(k, n))
    if n < 6:
        return 1
    best, best_score = 1, -1.0
    for kk in range(2, min(8, n - 1) + 1):
        labels = KMeans(n_clusters=kk, n_init=10, random_state=seed).fit_predict(Z)
        if len(set(labels)) > 1:
            score = silhouette_score(Z, labels)
            if score > best_score:
                best, best_score = kk, score
    return best


# ---------------------------------------------------------------- signals

def prr_stats(a, b, c, d):
    """PRR, 95% lower bound and Yates chi-square for the 2x2 table
           condition  no condition
    on drug      a          b
    not on drug  c          d          (0.5 is added to every cell when one is 0)"""
    if 0 in (a, b, c, d):
        a, b, c, d = a + 0.5, b + 0.5, c + 0.5, d + 0.5
    prr = (a / (a + b)) / (c / (c + d))
    se = math.sqrt(max(1 / a - 1 / (a + b) + 1 / c - 1 / (c + d), 0.0))
    low = math.exp(math.log(prr) - 1.96 * se)
    n = a + b + c + d
    den = (a + b) * (c + d) * (a + c) * (b + d)
    chi2 = (abs(a * d - b * c) - n / 2) ** 2 * n / den if den else 0.0
    return prr, low, chi2


class Signals:
    def __init__(self, patients: list[Patient], window_days: int, min_n: int):
        self.patients, self.window, self.min_n = patients, window_days, min_n
        self.n = len(patients)
        self.on_drug = defaultdict(set)
        self.has_cond = defaultdict(set)
        for i, p in enumerate(patients):
            for d in p.drugs:
                self.on_drug[d].add(i)
            for c in p.conditions:
                self.has_cond[c].add(i)
        self.indication_votes = Counter(pair for p in patients for pair in p.indications)

    def _counts_after(self, i, drug, cond):
        """Does patient i count as 'on drug, then got cond'? (None = can't tell, counted as yes)"""
        p = self.patients[i]
        if (drug, cond) in p.indications:
            return False
        start = p.drugs[drug][0]
        onset = p.conditions.get(cond)
        if start is None or onset is None:
            return None
        return 0 <= (onset - start).days <= self.window

    def pair(self, drug, cond):
        exposed = self.on_drug.get(drug, set())
        if not exposed or len(exposed) == self.n:
            return None
        a = dated = 0
        for i in exposed & self.has_cond.get(cond, set()):
            ok = self._counts_after(i, drug, cond)
            if ok is not False:
                a += 1
                dated += ok is True
        b = len(exposed) - a
        c = len(self.has_cond.get(cond, set()) - exposed)
        d = (self.n - len(exposed)) - c
        prr, low, chi2 = prr_stats(a, b, c, d)
        if a == 0:
            prr = low = chi2 = None  # nobody on the drug had it: a ratio would only reflect the 0.5 correction
        return {
            "drug": drug, "condition": cond, "n": a, "exposed": len(exposed),
            "rate_exposed": round(a / len(exposed), 3), "rate_unexposed": round(c / (self.n - len(exposed)), 3),
            "prr": None if prr is None else round(prr, 2), "prr_low": None if low is None else round(low, 2),
            "chi2": None if chi2 is None else round(chi2, 2), "dated": dated,
            "treats": self.indication_votes.get((drug, cond), 0),
            "signal": a >= self.min_n and prr >= 2 and chi2 >= 4,
        }

    def all(self):
        out = []
        for drug, exposed in self.on_drug.items():
            if len(exposed) < self.min_n:
                continue
            conds = Counter(c for i in exposed for c in self.patients[i].conditions)
            for cond, k in conds.items():
                if k >= self.min_n:
                    s = self.pair(drug, cond)
                    if s and s["n"] >= self.min_n:
                        out.append(s)
        out.sort(key=lambda s: (s["signal"], s["prr_low"], s["n"]), reverse=True)
        return out

    def indications(self):
        return [{"drug": d, "condition": c, "n": k} for (d, c), k in self.indication_votes.most_common()
                if k >= self.min_n]


# ---------------------------------------------------------------- build

def build(population: list[Patient], cases: list[Case] | None = None, *, min_support: int = 2,
          min_signal_n: int = 3, window_days: int = 90, k: int | None = None, seed: int = 42,
          source: str = "") -> dict:
    if not population:
        raise ValueError("No patients to analyse.")
    population = sorted(population, key=lambda p: p.id)
    n = len(population)
    emb = Embedding(population, min_support if n > 3 else 1, seed)

    Z = emb.z(emb.W)
    kk = _choose_k(Z, seed, k)
    if kk > 1:
        km = KMeans(n_clusters=kk, n_init=10, random_state=seed).fit(Z)
        labels, centers = km.labels_, km.cluster_centers_
    else:
        labels, centers = np.zeros(n, dtype=int), Z.mean(axis=0, keepdims=True)
    dist = np.linalg.norm(Z - centers[labels], axis=1)
    xy = emb.xy(emb.W)

    clusters = []
    overall = emb.X.mean(axis=0)
    for c in range(kk):
        members = labels == c
        prev = emb.X[members].mean(axis=0)
        lift = prev - overall
        top = [j for j in np.argsort(-lift) if prev[j] >= 0.5][:4] or list(np.argsort(-prev)[:3])
        clusters.append({
            "id": c, "size": int(members.sum()),
            "label": " · ".join(emb.names[j].split(":", 1)[1] for j in top[:3]),
            "features": [{"feature": emb.names[j].split(":", 1)[1], "kind": emb.names[j].split(":")[0],
                          "share": round(float(prev[j]), 2), "overall": round(float(overall[j]), 2)} for j in top],
        })

    sig = Signals(population, window_days, min_signal_n)
    signals = sig.all()
    strong = {(s["drug"], s["condition"]): s for s in signals if s["signal"]}

    # Population points for the map (keep it light: id, place, group, how unusual)
    dist_rank = np.argsort(np.argsort(dist)) / max(n - 1, 1)
    points = [{"id": p.id, "trial": p.trial, "cluster": int(labels[i]),
               "x": round(float(xy[i, 0]), 4), "y": round(float(xy[i, 1]), 4),
               "outlier": round(float(dist_rank[i]), 2),
               "signals": len([1 for d in p.drugs for c in p.conditions if (d, c) in strong])}
              for i, p in enumerate(population)]

    case_out = _cases(cases or [], population, emb, labels, centers, dist, sig, strong, clusters)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": source,
        "params": {"min_support": min_support, "min_signal_n": min_signal_n, "window_days": window_days,
                   "clusters": kk, "seed": seed},
        "counts": {"patients": n, "cases": len(case_out), "features": len(emb.names),
                   "signals": len(strong)},
        "caveats": CAVEATS,
        "axes": emb.axes(),
        "clusters": clusters,
        "trials": [{"name": t, "patients": c} for t, c in Counter(p.trial for p in population if p.trial).most_common()],
        "points": points,
        "cases": case_out,
        "signals": signals[:300],
        "indications": sig.indications()[:200],
        "graph": _graph(population, signals, sig.indications()),
    }


def _cases(cases, population, emb, labels, centers, dist, sig, strong, clusters):
    if not cases:
        return []
    by_id = {p.id: i for i, p in enumerate(population)}
    Wc = emb.weight(emb.binary([c.profile for c in cases]))
    Zc, XYc = emb.z(Wc), emb.xy(Wc)
    sim = Wc @ Wc.T
    np.fill_diagonal(sim, -1)
    spread = float(np.median(dist)) or 1.0
    out = []
    for i, case in enumerate(cases):
        row = by_id.get(case.person_id)
        if row is not None:      # the person is in the population: use their own place
            cluster, placed = int(labels[row]), "person"
        else:                    # place the case by its own drugs and conditions
            cluster = int(np.argmin(np.linalg.norm(centers - Zc[i], axis=1)))
            placed = "projected"
        unusual = float(np.linalg.norm(Zc[i] - centers[cluster]) / spread)

        pairs = []
        for raw, ingredients in case.drugs.items():
            for ing in ingredients:
                for reaction in case.reactions:
                    s = sig.pair(ing, reaction)
                    if s:
                        pairs.append({"drug": raw, "ingredient": ing, **{k: v for k, v in s.items() if k != "drug"}})
        pairs.sort(key=lambda s: (s["signal"], s["n"] > 0, s["prr_low"] or 0, s["n"]), reverse=True)
        # Only pairs seen in enough people can push a card up the queue
        seen = [s for s in pairs if s["n"] >= sig.min_n and (s["prr_low"] or 0) > 1]
        strength = min(1.0, math.log(seen[0]["prr_low"]) / math.log(4)) if seen else 0.0
        priority = round(100 * (0.7 * strength + 0.3 * min(1.0, unusual / 3)))
        similar = [{"id": cases[j].id, "similarity": round(float(sim[i, j]), 2)}
                   for j in np.argsort(-sim[i])[:4] if sim[i, j] > 0.15]
        out.append({
            "id": case.id, "person_id": case.person_id, "cluster": cluster, "cluster_label": clusters[cluster]["label"],
            "placed": placed, "x": round(float(XYc[i, 0]), 4), "y": round(float(XYc[i, 1]), 4),
            "unusual": round(unusual, 2), "priority": priority, "pairs": pairs[:12], "similar": similar,
        })
    return out


def _graph(population, signals, indications, max_nodes=60):
    drug_n = Counter(d for p in population for d in p.drugs)
    cond_n = Counter(c for p in population for c in p.conditions)
    strong = [s for s in signals if s["signal"]][:50]
    treats = indications[:40]
    drugs = {s["drug"] for s in strong} | {t["drug"] for t in treats}
    conds = {s["condition"] for s in strong} | {t["condition"] for t in treats}
    for d, _ in drug_n.most_common():         # fill up so small data still draws a picture
        if len(drugs) >= max_nodes // 2:
            break
        drugs.add(d)
    for c, _ in cond_n.most_common():
        if len(drugs) + len(conds) >= max_nodes:
            break
        conds.add(c)
    nodes = [{"id": f"drug:{d}", "label": d, "kind": "drug", "count": drug_n[d]} for d in sorted(drugs)]
    nodes += [{"id": f"cond:{c}", "label": c, "kind": "condition", "count": cond_n[c]} for c in sorted(conds)]
    links = [{"source": f"drug:{s['drug']}", "target": f"cond:{s['condition']}", "kind": "signal",
              "prr": s["prr"], "n": s["n"], "exposed": s["exposed"], "rate_exposed": s["rate_exposed"],
              "rate_unexposed": s["rate_unexposed"], "dated": s["dated"]} for s in strong]
    links += [{"source": f"drug:{t['drug']}", "target": f"cond:{t['condition']}", "kind": "treats", "n": t["n"]}
              for t in treats if t["drug"] in drugs and t["condition"] in conds]
    together = Counter()
    for p in population:
        ds = sorted(d for d in p.drugs if d in drugs)
        together.update((a, b) for i, a in enumerate(ds) for b in ds[i + 1:])
    links += [{"source": f"drug:{a}", "target": f"drug:{b}", "kind": "co_prescribed", "n": k}
              for (a, b), k in together.most_common(40) if k >= 2]
    return {"nodes": nodes, "links": links}