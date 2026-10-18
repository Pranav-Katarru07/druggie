import { Link } from "react-router";
import type { ReviewCard } from "./reviewCards";
import type { Decisions } from "./useDecisions";

function exportDecisions(cards: ReviewCard[], decisions: Decisions) {
  const rows = cards
    .filter((c) => decisions[c.key])
    .map((c) => ({
      case_id: c.patient.id,
      patient: c.patient.name ?? null,
      symptoms: c.patient.reactions,
      top_drug: c.clearTop ? c.ranked[0].drug.name : null,
      score: c.ranked[0].score,
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
  return (
    <div className="summary">
      <h2>All done</h2>
      <p className="muted">{cards.length} {cards.length === 1 ? "case" : "cases"} reviewed.</p>
      <div className="summary-actions">
        <button type="button" className="button dark" onClick={() => exportDecisions(cards, decisions)}>Export</button>
        <button type="button" className="button" onClick={onReset}>Start over</button>
        <Link to="/review" className="button">All drugs</Link>
      </div>
    </div>
  );
}
