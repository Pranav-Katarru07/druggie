"""Small backend for the "AI suggestion" button.

Keeps the API key off the browser: the React app POSTs to /api/suggest, this
server builds a prompt from the evidence extractData.py already collected, and
asks an OpenAI-compatible LLM (Gemini by default) for a draft.

Run:  python server.py   (reads settings from .env)
"""
import json
import os
import re
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_FILE = os.path.join(ROOT, "frontend", "public", "data.json")
PORT = 8000


def config():
    """Settings from .env (re-read on every request, so editing .env needs no restart),
    falling back to real environment variables."""
    values = {}
    path = os.path.join(ROOT, ".env")
    if os.path.exists(path):
        with open(path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    values[key.strip()] = value.strip()
    get = lambda k, default="": values.get(k) or os.environ.get(k, default)
    return {
        "api_key": get("LLM_API_KEY"),
        "base_url": get("LLM_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai").rstrip("/"),
        "model": get("LLM_MODEL", "gemini-3.8-flash"),
    }


SYSTEM_PROMPT = """You assist a drug-safety physician assessing which drug caused a patient's adverse event.
You will get one patient, ALL of their reactions, and numbered evidence items (E1, E2, ...) for each
drug and reaction pair. Treat the reactions together as one clinical picture: look for the drug that
best explains the combination (a drug whose known effects cover several reactions is a stronger
candidate than one that only matches a single reaction). Say which reactions each drug explains and
which reactions no drug explains well.
Evidence items are facts from the record (when each drug was started/stopped, what it was prescribed for)
and answers to Naranjo questions where they have been computed. Weigh timing carefully: a drug started
shortly before a symptom is a more plausible cause than one taken for years.

Rules:
- Use only the evidence given. Do not invent dates, lab values or history.
- Cite evidence ids for every reason. If you rely on general pharmacology knowledge, say so in the text and cite nothing.
- Say clearly what information is missing and how it limits the assessment.
- This is a draft for a physician, never a final determination.

Reply with JSON only, in this shape:
{
  "most_likely": "<drug name, or null if no drug stands out>",
  "confidence": "low" | "medium" | "high",
  "summary": "<2-3 sentences about the overall picture>",
  "drugs": [
    {"name": "<drug>", "assessment": "more likely" | "possible" | "less likely" | "can't tell",
     "explains": ["<reaction names this drug could account for>"],
     "reasons": [{"text": "<one reason>", "evidence": ["E1"]}]}
  ],
  "unexplained_reactions": ["<reactions no drug explains well>"],
  "missing_information": ["<what would change the assessment>"]
}"""

# The same shape as a JSON schema, so providers that support strict structured output enforce it
_STR_LIST = {"type": "array", "items": {"type": "string"}}
RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "most_likely": {"type": ["string", "null"]},
        "confidence": {"type": "string", "enum": ["low", "medium", "high"]},
        "summary": {"type": "string"},
        "drugs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "assessment": {"type": "string", "enum": ["more likely", "possible", "less likely", "can't tell"]},
                    "explains": _STR_LIST,
                    "reasons": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"text": {"type": "string"}, "evidence": _STR_LIST},
                            "required": ["text", "evidence"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["name", "assessment", "explains", "reasons"],
                "additionalProperties": False,
            },
        },
        "unexplained_reactions": _STR_LIST,
        "missing_information": _STR_LIST,
    },
    "required": ["most_likely", "confidence", "summary", "drugs", "unexplained_reactions", "missing_information"],
    "additionalProperties": False,
}


def build_prompt(patient, assessments):
    """Numbered evidence per drug: record facts (dates, indication) plus any computed question answers."""
    evidence = {}

    def add(drug, reaction, kind, text):
        eid = f"E{len(evidence) + 1}"
        evidence[eid] = {"drug": drug, "reaction": reaction, "kind": kind, "text": text}
        return f"    [{eid}] {text}"

    reactions = [a["reaction"] for a in assessments]
    lines = [f"Patient: {patient['sex']}, age {patient.get('age') or 'unknown'}",
             "Reactions: " + "; ".join(reactions) + (f" (began {patient['onset']})" if patient.get("onset") else ""), ""]
    for drug in patient["drugs"]:
        lines.append(f"Drug: {drug['name']}")
        if drug.get("started"):
            lines.append(add(drug["name"], "", "fact", f"Taken {drug['started']} to {drug.get('stopped') or 'ongoing'}"))
        if drug.get("indication"):
            lines.append(add(drug["name"], "", "fact", f"Prescribed for {drug['indication']}"))
        for a in assessments:
            candidate = next((c for c in a["drugs"] if c["name"] == drug["name"]), None)
            for ans in (candidate or {}).get("answers", []):
                lines.append(add(drug["name"], a["reaction"], "answer",
                                 f"{a['reaction']}: {ans['question']} {ans['answer']} ({ans['points']:+d}): {ans['why']}"))
        lines.append("")
    return "\n".join(lines), evidence


def post_chat(cfg, body):
    req = urllib.request.Request(
        cfg["base_url"] + "/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {cfg['api_key']}"},
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.load(resp)["choices"][0]["message"]["content"]


def looks_valid(result):
    """Free models sometimes return the right keys filled with junk ("...")."""
    try:
        return (isinstance(result.get("summary"), str) and len(result["summary"].strip(" .")) > 10
                and isinstance(result.get("drugs"), list)
                and all(isinstance(d, dict) and isinstance(d.get("reasons"), list)
                        and all(isinstance(r, dict) for r in d["reasons"])
                        and d.get("name", "").strip(" .") for d in result["drugs"]))
    except AttributeError:
        return False


def call_llm(user_prompt, cfg):
    body = {
        "model": cfg["model"],
        "messages": [{"role": "system", "content": SYSTEM_PROMPT},
                     {"role": "user", "content": user_prompt}],
        "response_format": {"type": "json_schema",
                            "json_schema": {"name": "suggestion", "strict": True, "schema": RESPONSE_SCHEMA}},
        "temperature": 0.2,
    }
    for attempt in range(2):
        try:
            content = post_chat(cfg, body)
        except urllib.error.HTTPError as e:
            if e.code != 400 or body["response_format"]["type"] == "json_object":
                raise
            # Provider doesn't support strict schemas; fall back to plain JSON mode
            body["response_format"] = {"type": "json_object"}
            content = post_chat(cfg, body)
        # Some models wrap JSON in ```json fences despite being asked not to
        content = re.sub(r"^```(?:json)?\s*|\s*```$", "", (content or "").strip())
        try:
            result = json.loads(content)
        except json.JSONDecodeError:
            result = None
        if isinstance(result, dict) and looks_valid(result):
            return result
    raise ValueError("the model returned malformed output twice; try again or switch LLM_MODEL in .env")


def suggest(patient_id, cfg):
    with open(DATA_FILE) as f:
        patients = json.load(f)
    patient = next((p for p in patients if p["id"] == patient_id), None)
    if not patient:
        return 404, {"error": "Patient not found."}
    assessments = [a for a in patient["assessment"] if a["assessable"]]
    if not assessments:
        return 400, {"error": "This patient has no clinical reactions to assess."}

    prompt, evidence = build_prompt(patient, assessments)
    result = call_llm(prompt, cfg)

    # Attach the cited evidence so the UI can show the source text,
    # and drop any ids the model made up
    # Models occasionally repeat a drug entry; keep the first of each
    seen = set()
    result["drugs"] = [d for d in result["drugs"]
                       if not (d["name"].lower() in seen or seen.add(d["name"].lower()))]
    for drug in result["drugs"]:
        for reason in drug["reasons"]:
            reason["evidence"] = [evidence[e] | {"id": e} for e in reason.get("evidence") or []
                                  if isinstance(e, str) and e in evidence]
    result["model"] = cfg["model"]
    return 200, result


# ---------- live log: print what the physician is looking at ----------

def log_view(req):
    """Print the raw Synthea rows and openFDA labels behind what's on screen.
    Decisions only print the short summary, since the raw data was shown when the card came up."""
    from raw_dump import dump_case  # imported lazily: it loads the Synthea CSVs on first use

    with open(DATA_FILE) as f:
        cases = json.load(f)
    event = req.get("event", "viewed")
    if req.get("person_id"):  # Patients page: every case for that person
        targets = [c for c in cases if c.get("person_id") == req["person_id"]]
    else:
        targets = [c for c in cases if c["id"] == req.get("case_id")]
    for case in targets:
        if event.startswith("Decision"):
            print(f"\n[{time.strftime('%H:%M:%S')}] {event}: case {case['id']} ({case.get('name', '')})", flush=True)
        else:
            print(dump_case(case, f"[{time.strftime('%H:%M:%S')}] {event}"), flush=True)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # keep the terminal for the case printouts, not request lines

    def _send(self, status, payload):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if self.path == "/api/log":
            try:
                length = int(self.headers.get("Content-Length", 0))
                log_view(json.loads(self.rfile.read(length) or b"{}"))
            except Exception as e:
                print(f"(log failed: {e})", flush=True)
            return self._send(200, {"ok": True})
        if self.path != "/api/suggest":
            return self._send(404, {"error": "Not found."})
        cfg = config()
        if not cfg["api_key"]:
            return self._send(500, {"error": "No API key. Paste it after LLM_API_KEY= in the .env file."})
        try:
            length = int(self.headers.get("Content-Length", 0))
            req = json.loads(self.rfile.read(length) or b"{}")
            status, payload = suggest(req.get("patient_id"), cfg)
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:300]
            status, payload = 502, {"error": f"The AI provider returned HTTP {e.code}: {detail}"}
        except (ValueError, KeyError, TypeError) as e:
            status, payload = 502, {"error": f"Couldn't read the AI's answer: {e}."}
        except Exception as e:  # keep the server alive and report the problem to the UI
            status, payload = 500, {"error": str(e)}
        self._send(status, payload)


if __name__ == "__main__":
    cfg = config()
    print(f"AI suggestion server on http://localhost:{PORT}  (model: {cfg['model']})")
    if not cfg["api_key"]:
        print("  Warning: LLM_API_KEY is empty; set it in .env")
    ThreadingHTTPServer(("127.0.0.1", PORT), Handler).serve_forever()