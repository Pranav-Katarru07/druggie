import type { Decision } from "./useDecisions";

export default function DecisionButtons({ onDecide }: { onDecide: (d: Decision) => void }) {
  return (
    <div className="actions">
      <button type="button" className="action no" onClick={() => onDecide("disagree")} aria-label="Disagree" title="Disagree (←)">✕</button>
      <button type="button" className="action yes" onClick={() => onDecide("agree")} aria-label="Agree" title="Agree (→)">✓</button>
    </div>
  );
}
