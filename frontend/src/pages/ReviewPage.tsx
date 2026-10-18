import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, Navigate, useParams } from "react-router";
import DecisionButtons from "../components/review/DecisionButtons";
import ReviewSummary from "../components/review/ReviewSummary";
import SwipeCard, { type SwipeCardHandle } from "../components/review/SwipeCard";
import { buildCards, groupByProbableDrug } from "../components/review/reviewCards";
import { DECISION_LABEL, useDecisions, type Decision } from "../components/review/useDecisions";
import { logView } from "../data/logView";
import { usePatientList } from "../data/patientsContext";
import "../components/review/Review.css";

const FLIP_MS = 500; // matches the .flip transition in Review.css
const EXPAND_AT_MS = 250; // start growing halfway through the flip, when the card is edge-on, so it reads as one move

// The swipe deck for one drug: the cases where it's the most probable cause
export default function ReviewPage() {
  const { drugKey } = useParams();
  const patients = usePatientList();
  const group = useMemo(
    () => groupByProbableDrug(buildCards(patients)).find((g) => g.key === drugKey),
    [patients, drugKey],
  );
  const cards = useMemo(() => group?.cards ?? [], [group]);
  const keys = useMemo(() => cards.map((c) => c.key), [cards]);
  const { decisions, decide, undo, reset } = useDecisions();
  const [cursor, setCursor] = useState<string | null>(null); // the card brought back by undo
  const topRef = useRef<SwipeCardHandle>(null);

  const remaining = cards.filter((c) => !decisions[c.key]);
  const current = (cursor && cards.find((c) => c.key === cursor)) || remaining[0];
  const next = remaining.find((c) => c.key !== current?.key);
  const doneCount = cards.length - remaining.length;

  // Tap: the card flips and, from halfway through, opens up to full size.
  // Mid-flip the card is edge-on and the next card shows through, so that one stays hidden until the flip back ends.
  const [flippedKey, setFlippedKey] = useState<string | null>(null);
  const [expanded, setExpanded] = useState(false);
  const [hideBehind, setHideBehind] = useState(false);
  const timer = useRef<number | undefined>(undefined);
  const currentKey = current?.key;
  const onFlipChange = useCallback(
    (flipped: boolean) => {
      setFlippedKey(flipped ? currentKey ?? null : null);
      window.clearTimeout(timer.current);
      if (flipped) {
        setHideBehind(true);
        timer.current = window.setTimeout(() => setExpanded(true), EXPAND_AT_MS);
      } else {
        setExpanded(false);
        timer.current = window.setTimeout(() => setHideBehind(false), FLIP_MS);
      }
    },
    [currentKey],
  );
  const isFlipped = !!current && flippedKey === current.key;

  // Print each card's details in the server terminal as it comes up (ref skips StrictMode's double run)
  const lastLogged = useRef<string | null>(null);
  useEffect(() => {
    if (current && lastLogged.current !== current.key) {
      lastLogged.current = current.key;
      logView({ event: "Card shown on Review", case_id: current.key });
    }
  }, [current]);

  function handleDecide(key: string, d: Decision) {
    decide(key, d);
    logView({ event: `Decision: ${DECISION_LABEL[d]}`, case_id: key });
    setCursor(null);
  }

  const handleUndo = useCallback(() => {
    const key = undo(keys);
    if (key) setCursor(key);
  }, [undo, keys]);

  // Keyboard: ← disagree, → agree, space flips, Esc closes, Z undoes
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const target = e.target as HTMLElement;
      if (target.closest("input, textarea")) return;
      if (e.key === "ArrowRight") topRef.current?.fly("agree");
      else if (e.key === "ArrowLeft") topRef.current?.fly("disagree");
      else if (e.key === "Escape" && isFlipped) topRef.current?.flip();
      else if (e.key === " " && !target.closest("button, summary, a")) {
        e.preventDefault();
        topRef.current?.flip();
      } else if (e.key.toLowerCase() === "z") handleUndo();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [handleUndo, isFlipped]);

  if (!group) return <Navigate to="/review" replace />;

  return (
    <div className="review">
      <div className="review-head">
        <div>
          <Link to="/review" className="text-button">← All drugs</Link>
          <h1>{group.name}</h1>
        </div>
        <span className="review-count">
          {doneCount}/{cards.length}
          {doneCount > 0 && <button type="button" className="text-button" onClick={handleUndo}>Undo</button>}
        </span>
      </div>

      {current ? (
        <div className="stage">
          <div className="stage-main">
            <div className={`deck ${hideBehind ? "solo" : ""} ${expanded ? "expanded" : ""}`}>
              {next && <SwipeCard key={`behind-${next.key}`} card={next} behind />}
              <SwipeCard
                key={current.key}
                ref={topRef}
                card={current}
                previous={decisions[current.key]?.decision}
                onDecide={(d) => handleDecide(current.key, d)}
                onFlipChange={onFlipChange}
                expanded={expanded}
              />
            </div>
            <DecisionButtons onDecide={(d) => topRef.current?.fly(d)} />
          </div>
        </div>
      ) : (
        <ReviewSummary cards={cards} decisions={decisions} onReset={() => { reset(keys); setCursor(null); }} />
      )}
    </div>
  );
}
