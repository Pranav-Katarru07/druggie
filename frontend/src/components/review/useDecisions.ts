import { useCallback, useEffect, useState } from "react";

export type Decision = "cause" | "not_cause" | "unsure";
export type Decisions = Record<string, { decision: Decision; at: string }>;

export const DECISION_LABEL: Record<Decision, string> = {
  cause: "Cause",
  not_cause: "Not the cause",
  unsure: "Can't tell",
};

const STORAGE_KEY = "druggie.decisions.v1";

function load(): Decisions {
  try {
    return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? "{}");
  } catch {
    return {};
  }
}

// Physician decisions, kept in this browser's localStorage
export function useDecisions() {
  const [decisions, setDecisions] = useState<Decisions>(load);

  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(decisions));
    } catch {
      /* storage blocked (private window): decisions just won't persist */
    }
  }, [decisions]);

  const decide = useCallback((key: string, decision: Decision) => {
    setDecisions((d) => ({ ...d, [key]: { decision, at: new Date().toISOString() } }));
  }, []);

  // Removes the most recent decision and returns its card key
  const undo = useCallback((): string | null => {
    const last = Object.entries(decisions).sort((a, b) => b[1].at.localeCompare(a[1].at))[0];
    if (!last) return null;
    setDecisions((d) => {
      const { [last[0]]: _removed, ...rest } = d;
      return rest;
    });
    return last[0];
  }, [decisions]);

  const reset = useCallback(() => setDecisions({}), []);

  return { decisions, decide, undo, reset };
}
