import AiSuggestion from "../ai/AiSuggestion";
import EvidenceForDrug from "../evidence/EvidenceForDrug";
import RoleBadge from "../evidence/RoleBadge";
import type { ReviewCard } from "./reviewCards";

export default function CardBack({ card, onFlipBack }: { card: ReviewCard; onFlipBack: () => void }) {
  const { patient, drug, perReaction } = card;
  return (
    <div className="back-inner">
      <div className="back-head">
        <div>
          <div className="back-title">
            <strong>{drug.name}</strong> <RoleBadge role={drug.role} />
          </div>
          {drug.label_via && <p className="muted back-sub">Label found by {drug.label_via}</p>}
        </div>
        <button type="button" className="text-button" onClick={onFlipBack}>↻ Flip back</button>
      </div>

      <div className="back-scroll">
        {perReaction.map(({ reaction, candidate }) => (
          <section key={reaction} className="back-section">
            <h3>{reaction}</h3>
            <EvidenceForDrug candidate={candidate} />
          </section>
        ))}

        <section className="back-section">
          <h3>AI view of the whole patient</h3>
          <AiSuggestion patientId={patient.id} highlight={drug.name} />
        </section>
      </div>
    </div>
  );
}
