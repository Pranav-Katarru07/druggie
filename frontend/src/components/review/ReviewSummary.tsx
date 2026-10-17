import type { ReviewCard } from "./reviewCards";
import { DECISION_LABEL, type Decisions } from "./useDecisions";

function exportDecisions(cards: ReviewCard[], decisions: Decisions) {
  const rows = cards
    .filter((c) => decisions[c.key])
    .map((c) => ({
      patient_id: c.patient.id,
      drug: c.drug.name,
      reactions: c.perReaction.map((r) => r.reaction),
      decision: decisions[c.key].decision,
      decided_at: decisions[c.key].at,
    }));
  const url = URL.createObjectURL(new Blob([JSON.stringify(rows, null, 2)], { type: "application/json" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = "druggie-decisions.json";
  a.click();
  URL.revokeObjectURL(url);
}

export default function ReviewSummary({ cards, decisions, onReset }: { cards: ReviewCard[]; decisions: Decisions; onReset: () => void }) {
  const counts = { cause: 0, not_cause: 0, unsure: 0 };
  for (const c of cards) {
    const d = decisions[c.key]?.decision;
    if (d) counts[d]++;
  }

  return (
    <div className="summary">
      <h2>All cards reviewed</h2>
      <p className="muted">Decisions are saved in this browser. Pick any card in the queue to change it.</p>
      <div className="summary-counts">
        {(Object.keys(counts) as (keyof typeof counts)[]).map((k) => (
          <div key={k} className={`stat ${k === "cause" ? "for" : k === "not_cause" ? "against" : ""}`}>
            <strong>{counts[k]}</strong>
            <span>{DECISION_LABEL[k]}</span>
          </div>
        ))}
      </div>
      <div className="summary-actions">
        <button type="button" className="button primary" onClick={() => exportDecisions(cards, decisions)}>
          Export decisions (JSON)
        </button>
        <button type="button" className="text-button" onClick={onReset}>Start over</button>
      </div>
    </div>
  );
}
