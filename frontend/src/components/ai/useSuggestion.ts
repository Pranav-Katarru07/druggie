import { useState } from "react";
import type { Suggestion } from "../../types";

// AI results by patient, so a patient's drug cards (and the Browse page) share one request
const cache = new Map<string, Suggestion>();

export type SuggestionState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "done"; result: Suggestion };

export function useSuggestion(patientId: string) {
  const cached = cache.get(patientId);
  const [state, setState] = useState<SuggestionState>(cached ? { status: "done", result: cached } : { status: "idle" });

  async function run() {
    setState({ status: "loading" });
    try {
      const resp = await fetch("/api/suggest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ patient_id: patientId }),
      });
      const data = await resp.json().catch(() => ({ error: "The AI server isn't running. Start it with `python3 server.py`." }));
      if (!resp.ok) throw new Error(data.error ?? `HTTP ${resp.status}`);
      cache.set(patientId, data);
      setState({ status: "done", result: data });
    } catch (e) {
      setState({ status: "error", message: e instanceof Error ? e.message : String(e) });
    }
  }

  return { state, run };
}
