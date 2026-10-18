import { useCallback, useEffect, useState } from "react";

// Agree / disagree with the card's most probable drug
export type Decision = "agree" | "disagree";
export type Decisions = Record<string, { decision: Decision; at: string }>;

export const DECISION_LABEL: Record<Decision, string> = {
  agree: "Agree",
  disagree: "Disagree",
};

const STORAGE_KEY = "druggie.decisions.v2"; // v1 was one decision per drug

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

  // Removes the most recent decision (among `keys`, when given) and returns its card key
  const undo = useCallback((keys?: string[]): string | null => {
    const last = Object.entries(decisions)
      .filter(([k]) => !keys || keys.includes(k))
      .sort((a, b) => b[1].at.localeCompare(a[1].at))[0];
    if (!last) return null;
    setDecisions((d) => {
      const { [last[0]]: _removed, ...rest } = d;
      return rest;
    });
    return last[0];
  }, [decisions]);

  // Clears the decisions for `keys` (one drug's cases), or all of them
  const reset = useCallback((keys?: string[]) => {
    setDecisions((d) => (keys ? Object.fromEntries(Object.entries(d).filter(([k]) => !keys.includes(k))) : {}));
  }, []);

  return { decisions, decide, undo, reset };
}
