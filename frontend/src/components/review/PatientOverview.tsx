import RoleBadge from "../evidence/RoleBadge";
import { cardStats, type ReviewCard } from "./reviewCards";
import { DECISION_LABEL, type Decisions } from "./useDecisions";

// Side panel: the current patient's other drugs, to compare competing explanations at a glance
export default function PatientOverview({ card, cards, decisions, onSelect }: {
  card: ReviewCard;
  cards: ReviewCard[];
  decisions: Decisions;
  onSelect: (key: string) => void;
}) {
  const siblings = cards.filter((c) => c.patient.id === card.patient.id);
  const p = card.patient;

  return (
    <aside className="overview" aria-label="Patient overview">
      <h2 className="queue-title">This patient</h2>
      <div className="overview-block">
        <strong>Patient {p.id}</strong>
        <span className="muted">{p.sex}, {p.age ? `${p.age} yrs` : "age unknown"}</span>
        <div className="chips">
          {p.reactions.map((r) => <span key={r} className="chip reaction-chip">{r}</span>)}
        </div>
      </div>

      <h3 className="overview-sub">Drugs ({siblings.length})</h3>
      <ul className="overview-drugs">
        {siblings.map((c) => {
          const s = cardStats(c);
          const d = decisions[c.key]?.decision;
          return (
            <li key={c.key}>
              <button
                type="button"
                className={`overview-drug ${c.key === card.key ? "current" : ""}`}
                onClick={() => onSelect(c.key)}
              >
                <span className="overview-drug-head">
                  <strong>{c.drug.name}</strong>
                  <RoleBadge role={c.drug.role} />
                </span>
                <span className="overview-drug-stats">
                  <span>{c.drug.label_found ? `${s.onLabel}/${c.perReaction.length} on label` : "no label"}</span>
                  <span className="for">+{s.forCount}</span>
                  <span className="against">−{s.againstCount}</span>
                  {d && <span className={`queue-verdict ${d}`}>{DECISION_LABEL[d]}</span>}
                </span>
              </button>
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
