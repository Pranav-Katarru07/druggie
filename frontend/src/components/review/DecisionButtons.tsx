import type { Decision } from "./useDecisions";

export default function DecisionButtons({ onDecide }: { onDecide: (d: Decision) => void }) {
  return (
    <div className="actions">
      <button type="button" className="action no" onClick={() => onDecide("not_cause")}>
        <span aria-hidden>✕</span>Not the cause
      </button>
      <button type="button" className="action unsure" onClick={() => onDecide("unsure")}>
        <span aria-hidden>?</span>Can't tell
      </button>
      <button type="button" className="action yes" onClick={() => onDecide("cause")}>
        <span aria-hidden>✓</span>Cause
      </button>
    </div>
  );
}
