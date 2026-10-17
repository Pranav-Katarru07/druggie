import { useEffect, useMemo, useRef, useState } from "react";
import DecisionButtons from "../components/review/DecisionButtons";
import PatientOverview from "../components/review/PatientOverview";
import ReviewQueue from "../components/review/ReviewQueue";
import ReviewSummary from "../components/review/ReviewSummary";
import SwipeCard, { type SwipeCardHandle } from "../components/review/SwipeCard";
import { buildCards } from "../components/review/reviewCards";
import { useDecisions, type Decision } from "../components/review/useDecisions";
import { usePatientList } from "../data/patientsContext";
import "../components/review/Review.css";

export default function ReviewPage() {
  const patients = usePatientList();
  const cards = useMemo(() => buildCards(patients), [patients]);
  const { decisions, decide, undo, reset } = useDecisions();
  const [cursor, setCursor] = useState<string | null>(null); // card picked from the queue
  const topRef = useRef<SwipeCardHandle>(null);

  const remaining = cards.filter((c) => !decisions[c.key]);
  const current = (cursor && cards.find((c) => c.key === cursor)) || remaining[0];
  const next = remaining.find((c) => c.key !== current?.key);
  const doneCount = cards.length - remaining.length;

  function handleDecide(key: string, d: Decision) {
    decide(key, d);
    setCursor(null);
  }

  function handleUndo() {
    const key = undo();
    if (key) setCursor(key); // bring the undone card back to the top
  }

  // Keyboard: ← → ↑ decide, space flips, Z undoes
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement;
      if (target.closest("input, textarea")) return;
      if (e.key === "ArrowRight") topRef.current?.fly("cause");
      else if (e.key === "ArrowLeft") topRef.current?.fly("not_cause");
      else if (e.key === "ArrowUp") topRef.current?.fly("unsure");
      else if (e.key === " " && !target.closest("button, summary, a")) {
        e.preventDefault();
        topRef.current?.flip();
      } else if (e.key.toLowerCase() === "z") {
        const key = undo();
        if (key) setCursor(key);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [undo]);

  if (cards.length === 0) return <p className="empty">No patients with clinical reactions to review.</p>;

  return (
    <div className="review-page">
      <ReviewQueue cards={cards} decisions={decisions} currentKey={current?.key} onSelect={setCursor} />

      <section className="stage" aria-label="Review card">
        <div className="stage-top">
          <div className="progress" role="progressbar" aria-valuemin={0} aria-valuemax={cards.length} aria-valuenow={doneCount}>
            <div className="progress-bar" style={{ width: `${(doneCount / cards.length) * 100}%` }} />
          </div>
          <div className="progress-text">
            <span>{doneCount} of {cards.length} reviewed</span>
            {doneCount > 0 && <button type="button" className="text-button" onClick={handleUndo}>Undo last</button>}
          </div>
        </div>

        {current ? (
          <>
            <div className="deck">
              {next && <SwipeCard key={`behind-${next.key}`} card={next} behind />}
              <SwipeCard
                key={current.key}
                ref={topRef}
                card={current}
                previous={decisions[current.key]?.decision}
                onDecide={(d) => handleDecide(current.key, d)}
              />
            </div>
            <DecisionButtons onDecide={(d) => topRef.current?.fly(d)} />
            <p className="hint">Tap the card to flip · swipe right for cause, left for not · keys ← → ↑ · space flips · Z undoes</p>
          </>
        ) : (
          <ReviewSummary cards={cards} decisions={decisions} onReset={() => { reset(); setCursor(null); }} />
        )}
      </section>

      {current && <PatientOverview card={current} cards={cards} decisions={decisions} onSelect={setCursor} />}
    </div>
  );
}
