"""Clean up raw drug and condition names so the same thing gets one name.

Synthea / RxNorm style medication strings look like
  "24 HR Metformin hydrochloride 500 MG Extended Release Oral Tablet"
  "insulin isophane  human 70 UNT/ML / insulin  regular  human 30 UNT/ML Injectable Suspension [Humulin]"
and become ingredient names: "metformin", "insulin isophane human", "insulin regular human".

SNOMED style condition strings look like "Essential hypertension (disorder)".
Social and admin entries such as "Full-time employment (finding)" are not clinical
events and are dropped, so they can't show up as fake drug reactions.
"""
import re

# Leading package sizes: "24 HR", "120 ACTUAT", "1 ML", "0.4 ML", "28 DAY"
_PACKAGE = re.compile(r"^\s*\d+(?:\.\d+)?\s*(?:HR|ML|ACTUAT|DAY|MCG|MG)\b\s*", re.I)
_BRAND = re.compile(r"\[[^\]]*\]|\((?:usp|nf|bp)\)", re.I)
_SPACES = re.compile(r"\s+")
# Salt words that don't change which drug it is
_SALTS = {"hydrochloride", "hcl", "succinate", "tartrate", "besylate", "maleate", "mesylate", "fumarate",
          "monohydrate", "dihydrate", "anhydrous"}

_TAG = re.compile(r"\s*\(([^()]*)\)\s*$")
# Findings and situations that describe someone's life, not their health
_SOCIAL = re.compile(
    r"employment|labor force|educat|higher education|housing|homeless|transport|social|isolation|"
    r"stress|criminal|incarcerat|refugee|military|insurance|income|unemploy|medication review|"
    r"risk activity|intimate partner|violence|victim|reports of violence|has a criminal|lack of access|"
    r"limited social|not in labor|received|served|serving|dental|pregnancy history|"
    r"history of|misuses drugs",
    re.I,
)
# Semantic tags that are never clinical events
_DROP_TAGS = {"situation", "person", "procedure", "observable entity", "qualifier value", "regime/therapy"}


def drug_names(raw: str) -> list[str]:
    """One raw medication string -> list of ingredient names (combination products give several)."""
    if not raw:
        return []
    text = _BRAND.sub("", raw)
    names = []
    # Kits: "{28 (norethindrone 0.35 MG Oral Tablet) } Pack" -> "norethindrone 0.35 MG Oral Tablet"
    text = re.sub(r"\)\s*\}.*$", "", text)
    for part in re.split(r"\s/\s|\)\s*/\s*", text):
        part = re.sub(r"^[\s{(]*\d+\s*\(", "", part).strip(" {}()")
        part = re.sub(r"^(?:NDA|ANDA|BLA)\d+\s+", "", part, flags=re.I)
        if re.match(r"inert ingredients?\b", part, re.I):
            continue
        while _PACKAGE.match(part):
            part = _PACKAGE.sub("", part, count=1)
        # The ingredient is everything before the first number (the strength)
        m = re.search(r"\s\d", " " + part)
        head = part[: m.start() - 1] if m and m.start() > 0 else part
        words = [w for w in _SPACES.sub(" ", head).strip().lower().split(" ") if w]
        while words and words[-1] in _SALTS:
            words.pop()
        if words:
            names.append(" ".join(words))
    return names


def condition_name(raw: str) -> str | None:
    """One raw condition string -> clean name, or None when it isn't a clinical event."""
    if not raw:
        return None
    text = _SPACES.sub(" ", raw).strip()
    tag = None
    m = _TAG.search(text)
    if m:
        tag = m.group(1).strip().lower()
        text = text[: m.start()].strip()
    if tag in _DROP_TAGS:
        return None
    if tag == "finding" and _SOCIAL.search(text):
        return None
    if tag is None and _SOCIAL.search(text):
        return None
    return text[0].upper() + text[1:] if text else None
