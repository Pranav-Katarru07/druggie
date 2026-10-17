import type { ReviewCard } from "./reviewCards";
import { DECISION_LABEL, type Decisions } from "./useDecisions";

interface Props {
  cards: ReviewCard[];
  decisions: Decisions;
  currentKey?: string;
  onSelect: (key: string) => void;
}

// Sidebar listing every card by patient; click one to jump to it
export default function ReviewQueue({ cards, decisions, currentKey, onSelect }: Props) {
  const byPatient = new Map<string, ReviewCard[]>();
  for (const c of cards) byPatient.set(c.patient.id, [...(byPatient.get(c.patient.id) ?? []), c]);

  return (
    <nav className="queue" aria-label="Review queue">
      <h2 className="queue-title">Queue</h2>
      {[...byPatient.entries()].map(([id, pcards]) => {
        const done = pcards.filter((c) => decisions[c.key]).length;
        return (
          <div key={id} className="queue-patient">
            <div className="queue-patient-head">
              <span>Patient {id}</span>
              <span className="muted">{done}/{pcards.length}</span>
            </div>
            <ul>
              {pcards.map((c) => {
                const d = decisions[c.key]?.decision;
                return (
                  <li key={c.key}>
                    <button
                      type="button"
                      className={`queue-item ${c.key === currentKey ? "current" : ""}`}
                      onClick={() => onSelect(c.key)}
                      aria-current={c.key === currentKey}
                    >
                      <span className={`dot ${d ?? "pending"}`} aria-hidden />
                      <span className="queue-drug">{c.drug.name}</span>
                      {d && <span className={`queue-verdict ${d}`}>{DECISION_LABEL[d]}</span>}
                    </button>
                  </li>
                );
              })}
            </ul>
          </div>
        );
      })}
    </nav>
  );
}
