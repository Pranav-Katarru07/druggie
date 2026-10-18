import { useCallback, useEffect, useImperativeHandle, useRef, useState, type PointerEvent, type Ref } from "react";
import CardBack from "./CardBack";
import CardFront from "./CardFront";
import type { ReviewCard } from "./reviewCards";
import { DECISION_LABEL, type Decision } from "./useDecisions";

const SWIPE_THRESHOLD = 110; // px of horizontal drag that counts as a decision
const FLY_MS = 280;

export interface SwipeCardHandle {
  fly: (d: Decision) => void;
  flip: () => void;
}

interface Props {
  card: ReviewCard;
  previous?: Decision; // set when revisiting a card that was already decided
  behind?: boolean; // the next card, peeking out under the current one
  onDecide?: (d: Decision) => void;
  onFlipChange?: (flipped: boolean) => void;
  expanded?: boolean; // the back has opened up to full size: no tap-to-flip or drag, so its pages can be used
  ref?: Ref<SwipeCardHandle>;
}

export default function SwipeCard({ card, previous, behind, onDecide, onFlipChange, expanded, ref }: Props) {
  const [flipped, setFlipped] = useState(false);
  useEffect(() => onFlipChange?.(flipped), [flipped, onFlipChange]);
  const [drag, setDrag] = useState({ dx: 0, dy: 0, active: false });
  const [leaving, setLeaving] = useState<Decision | null>(null);
  const start = useRef<{ x: number; y: number; moved: boolean } | null>(null);

  const fly = useCallback(
    (d: Decision) => {
      if (leaving || !onDecide) return;
      setLeaving(d);
      setTimeout(() => onDecide(d), FLY_MS);
    },
    [leaving, onDecide],
  );

  useImperativeHandle(ref, () => ({ fly, flip: () => setFlipped((f) => !f) }), [fly]);

  function onPointerDown(e: PointerEvent<HTMLDivElement>) {
    if (behind || leaving) return;
    // Let buttons, links and expandable sections work normally
    if ((e.target as HTMLElement).closest("button, a, summary, details[open] *")) return;
    start.current = { x: e.clientX, y: e.clientY, moved: false };
    if (expanded) return; // open card: a tap closes it, but no dragging (so its pages can scroll)
    try {
      e.currentTarget.setPointerCapture(e.pointerId); // keep tracking if the pointer leaves the card
    } catch {
      /* not supported for this pointer; dragging still works while over the card */
    }
  }

  function onPointerMove(e: PointerEvent<HTMLDivElement>) {
    if (!start.current) return;
    const dx = e.clientX - start.current.x;
    const dy = e.clientY - start.current.y;
    if (Math.abs(dx) > 5 || Math.abs(dy) > 5) start.current.moved = true;
    if (!expanded) setDrag({ dx, dy: dy * 0.2, active: true });
  }

  function onPointerUp() {
    if (!start.current) return;
    const { moved } = start.current;
    start.current = null;
    if (drag.dx > SWIPE_THRESHOLD) fly("agree");
    else if (drag.dx < -SWIPE_THRESHOLD) fly("disagree");
    else if (!moved && !window.getSelection()?.toString()) setFlipped((f) => !f); // a tap flips (or closes) the card
    setDrag({ dx: 0, dy: 0, active: false });
  }

  function cancelDrag() {
    start.current = null;
    setDrag({ dx: 0, dy: 0, active: false });
  }

  let transform = `translate(${drag.dx}px, ${drag.dy}px) rotate(${drag.dx / 18}deg)`;
  if (leaving === "agree") transform = "translate(130vw, 40px) rotate(25deg)";
  if (leaving === "disagree") transform = "translate(-130vw, 40px) rotate(-25deg)";

  const stamp: Decision | null = leaving ?? (drag.dx > 20 ? "agree" : drag.dx < -20 ? "disagree" : null);
  const stampOpacity = leaving ? 1 : Math.min(Math.abs(drag.dx) / SWIPE_THRESHOLD, 1);

  return (
    <div
      className={`swipe ${behind ? "behind" : ""} ${drag.active ? "dragging" : ""} ${expanded ? "expanded" : ""}`}
      style={behind ? undefined : { transform }}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={cancelDrag}
      aria-hidden={behind}
    >
      <div className={`flip ${flipped ? "flipped" : ""}`}>
        <div className="face front">
          <CardFront card={card} previous={previous} />
        </div>
        {!behind && (
          <div className="face back">
            <CardBack card={card} onFlipBack={() => setFlipped(false)} />
          </div>
        )}
      </div>
      {stamp && !behind && (
        <div className={`stamp ${stamp}`} style={{ opacity: stampOpacity }}>
          {DECISION_LABEL[stamp]}
        </div>
      )}
    </div>
  );
}
