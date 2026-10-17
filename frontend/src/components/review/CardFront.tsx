import RoleBadge from "../evidence/RoleBadge";
import { cardStats, type ReviewCard } from "./reviewCards";
import { DECISION_LABEL, type Decision } from "./useDecisions";

export default function CardFront({ card, previous }: { card: ReviewCard; previous?: Decision }) {
  const { patient, drug, perReaction } = card;
  const { onLabel, forCount, againstCount } = cardStats(card);

  return (
    <div className="front-inner">
      <div className="front-top">
        <span>Patient {patient.id}</span>
        <span>{patient.sex}, {patient.age ? `${patient.age} yrs` : "age unknown"}</span>
      </div>

      <div>
        <span className="eyebrow">Reactions{patient.onset && ` · began ${patient.onset}`}</span>
        <div className="chips">
          {perReaction.map((r) => <span key={r.reaction} className="chip reaction-chip">{r.reaction}</span>)}
        </div>
      </div>

      <div className="question">
        <span className="eyebrow">Is this drug the cause?</span>
        <h2 className="drug-name">{drug.name}</h2>
        <div className="question-meta">
          <RoleBadge role={drug.role} />
          {drug.indication && <span className="muted">for {drug.indication.toLowerCase()}</span>}
        </div>
        {drug.started && (
          <p className="muted question-count">
            Taken {drug.started} → {drug.stopped ?? "ongoing"}
          </p>
        )}
        <p className="muted question-count">
          Drug {card.indexInPatient + 1} of {patient.drugs.length} for this patient
        </p>
        {previous && <span className={`verdict ${previous}`}>Previously: {DECISION_LABEL[previous]}</span>}
      </div>

      <div className="front-stats">
        <div className="stat">
          <strong>{drug.label_found ? `${onLabel}/${perReaction.length}` : "—"}</strong>
          <span>{drug.label_found ? "reactions on label" : "no label found"}</span>
        </div>
        <div className="stat for">
          <strong>{forCount}</strong>
          <span>points for</span>
        </div>
        <div className="stat against">
          <strong>{againstCount}</strong>
          <span>points against</span>
        </div>
      </div>

      <p className="flip-hint">Tap to see the evidence ↻</p>
    </div>
  );
}
