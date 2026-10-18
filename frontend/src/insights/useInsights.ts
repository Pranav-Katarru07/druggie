import { useEffect, useState } from "react";
import type { CaseInsight, Insights } from "./types";

export type InsightsState =
  | { status: "loading" }
  | { status: "missing"; message: string }
  | { status: "ready"; data: Insights; byCase: Map<string, CaseInsight> };

// Where the insights come from:
//   - Supabase table "insights" (row id "latest") when VITE_SUPABASE_URL and VITE_SUPABASE_ANON_KEY are set
//   - otherwise /insights.json (written by `python -m analytics`)
// The rest of the app works without them; insight panels just stay hidden.
const url = import.meta.env.VITE_SUPABASE_URL as string | undefined;
const anonKey = import.meta.env.VITE_SUPABASE_ANON_KEY as string | undefined;

async function fetchInsights(): Promise<Insights> {
  if (url && anonKey) {
    try {
      const r = await fetch(`${url.replace(/\/$/, "")}/rest/v1/insights?id=eq.latest&select=data`, {
        headers: { apikey: anonKey, Authorization: `Bearer ${anonKey}` },
      });
      if (r.ok) {
        const rows: { data: Insights }[] = await r.json();
        if (rows[0]) return rows[0].data;
      }
    } catch {
      /* fall through to the file */
    }
  }
  const r = await fetch("/insights.json");
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

let shared: Promise<InsightsState> | null = null;

function load(): Promise<InsightsState> {
  shared ??= fetchInsights()
    .then((data): InsightsState => ({ status: "ready", data, byCase: new Map(data.cases.map((c) => [c.id, c])) }))
    .catch(() => ({ status: "missing", message: "No insights yet. Run `python -m analytics` to create them." }));
  return shared;
}

// Loaded once and shared by every component that asks
export function useInsights(): InsightsState {
  const [state, setState] = useState<InsightsState>({ status: "loading" });
  useEffect(() => {
    let alive = true;
    load().then((s) => alive && setState(s));
    return () => {
      alive = false;
    };
  }, []);
  return state;
}

// Plain-English helpers shared by the card panel and the Insights page
export function percent(rate: number) {
  if (rate === 0) return "0%";
  if (rate < 0.01) return "<1%";
  return `${Math.round(rate * 100)}%`;
}

export function times(prr: number | null) {
  if (prr === null) return "–";
  return prr >= 10 ? `${Math.round(prr)}×` : `${prr.toFixed(1)}×`;
}
