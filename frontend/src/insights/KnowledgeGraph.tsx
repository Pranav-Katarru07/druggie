import { forceCollide, forceLink, forceManyBody, forceSimulation, forceX, forceY, type SimulationNodeDatum } from "d3-force";
import { useMemo, useState } from "react";
import { Link } from "react-router";
import { percent, times } from "./useInsights";
import type { GraphLink, GraphNode } from "./types";

const W = 760;
const H = 520;
const short = (label: string) => (label.length > 30 ? `${label.slice(0, 28)}…` : label);

type SimNode = GraphNode & SimulationNodeDatum & { r: number };
type SimLink = Omit<GraphLink, "source" | "target"> & { source: SimNode; target: SimNode; i: number };

export interface DeckCase { id: string; label: string; href: string }

// Drugs (filled) and conditions (outlined), linked by "possible reaction" (solid, thicker = stronger),
// "prescribed for" (dashed) and "often taken together" (faint).
// Hover a circle or a line for a plain-English explanation; tap a circle to pin it and follow its links
// into the review deck. The layout is computed once, so the same data always draws the same picture.
export default function KnowledgeGraph({ nodes, links, patients, windowDays, casesFor }: {
  nodes: GraphNode[];
  links: GraphLink[];
  patients: number; // population size, for "44 of 184 patients"
  windowDays: number;
  casesFor?: (node: GraphNode) => DeckCase[]; // review cases that involve this drug or condition
}) {
  const [hovered, setHovered] = useState<{ node?: string; link?: number } | null>(null);
  const [pinned, setPinned] = useState<string | null>(null);

  const layout = useMemo(() => {
    const maxCount = Math.max(1, ...nodes.map((n) => n.count));
    const simNodes: SimNode[] = nodes.map((n) => ({ ...n, r: 5 + 11 * Math.sqrt(n.count / maxCount) }));
    const byId = new Map(simNodes.map((n) => [n.id, n]));
    const simLinks = links
      .filter((l) => byId.has(l.source) && byId.has(l.target))
      .map((l, i) => ({ ...l, i, source: byId.get(l.source)!, target: byId.get(l.target)! })) as SimLink[];

    const sim = forceSimulation(simNodes)
      .force("link", forceLink<SimNode, SimLink>(simLinks).distance((l) => (l.kind === "co_prescribed" ? 70 : 55))
        .strength((l) => (l.kind === "co_prescribed" ? 0.15 : 0.6)))
      .force("charge", forceManyBody().strength(-140))
      .force("x", forceX(0).strength(0.06))
      .force("y", forceY(0).strength(0.09))
      .force("collide", forceCollide<SimNode>((n) => n.r + 6))
      .stop();
    for (let i = 0; i < 320; i++) sim.tick();

    const xs = simNodes.map((n) => n.x ?? 0);
    const ys = simNodes.map((n) => n.y ?? 0);
    const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
    const pad = 70;
    const k = Math.min((W - 2 * pad) / (x1 - x0 || 1), (H - 2 * pad) / (y1 - y0 || 1));
    for (const n of simNodes) {
      n.x = W / 2 + ((n.x ?? 0) - (x0 + x1) / 2) * k;
      n.y = H / 2 + ((n.y ?? 0) - (y0 + y1) / 2) * k;
    }

    // Label signal nodes first, then the biggest; a label goes right or left of its circle,
    // and is skipped if both sides would overlap something already placed
    const inSignal = new Set(simLinks.filter((l) => l.kind === "signal").flatMap((l) => [l.source.id, l.target.id]));
    const order = [...simNodes].sort((a, b) => Number(inSignal.has(b.id)) - Number(inSignal.has(a.id)) || b.count - a.count);
    const taken = simNodes.map((n) => ({ id: n.id, x0: n.x! - n.r, x1: n.x! + n.r, y0: n.y! - n.r, y1: n.y! + n.r }));
    const labelled = new Map<string, "right" | "left">();
    for (const n of order) {
      if (labelled.size >= 22) break;
      const width = short(n.label).length * 6.2 + 4;
      const right = { id: n.id, x0: n.x! + n.r + 3, x1: n.x! + n.r + 3 + width, y0: n.y! - 8, y1: n.y! + 8 };
      const left = { id: n.id, x0: n.x! - n.r - 3 - width, x1: n.x! - n.r - 3, y0: n.y! - 8, y1: n.y! + 8 };
      const free = (box: typeof right) => box.x0 > 4 && box.x1 < W - 4 &&
        !taken.some((b) => b.id !== n.id && b.x0 < box.x1 && box.x0 < b.x1 && b.y0 < box.y1 && box.y0 < b.y1);
      const box = free(right) ? right : free(left) ? left : null;
      if (box) {
        labelled.set(n.id, box === right ? "right" : "left");
        taken.push(box);
      }
    }
    return { simNodes, simLinks, byId, labelled };
  }, [nodes, links]);

  // What's being explained: the hovered thing, else the pinned circle
  const focusNode = hovered?.node ?? (hovered?.link === undefined ? pinned : null);
  const focusLink = hovered?.link !== undefined ? layout.simLinks[hovered.link] : null;

  const lit = useMemo(() => {
    if (focusLink) return new Set([focusLink.source.id, focusLink.target.id]);
    if (!focusNode) return null;
    const ids = new Set([focusNode]);
    for (const l of layout.simLinks) {
      if (l.kind === "co_prescribed") continue;
      if (l.source.id === focusNode) ids.add(l.target.id);
      if (l.target.id === focusNode) ids.add(l.source.id);
    }
    return ids;
  }, [focusNode, focusLink, layout]);
  const isLit = (id: string) => !lit || lit.has(id);
  const linkLit = (l: SimLink) => (focusLink ? l === focusLink : isLit(l.source.id) && isLit(l.target.id));

  return (
    <div className="kg">
      <div className="kg-key" aria-hidden>
        <span><i className="kg-key-drug" /> Drug</span>
        <span><i className="kg-key-cond" /> Condition</span>
        <span><i className="kg-key-signal" /> Possible reaction (thicker = stronger)</span>
        <span><i className="kg-key-treats" /> Prescribed for</span>
        <span><i className="kg-key-co" /> Often taken together</span>
      </div>
      <div className="kg-body">
        <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Knowledge graph of drugs and conditions"
          onClick={() => setPinned(null)} onMouseLeave={() => setHovered(null)}>
          <rect width={W} height={H} rx={16} className="kg-bg" />
          <g>
            {layout.simLinks.map((l) => {
              const width = l.kind === "signal" ? 1.5 + Math.log2(Math.max(1, l.prr ?? 1)) * 0.8 : l.kind === "treats" ? 1.5 : 1;
              return (
                <g key={l.i} className={linkLit(l) ? "" : "dim"}>
                  <line x1={l.source.x} y1={l.source.y} x2={l.target.x} y2={l.target.y}
                    className={`kg-link ${l.kind}${focusLink === l ? " on" : ""}`} strokeWidth={width} />
                  {l.kind !== "co_prescribed" && (
                    <line x1={l.source.x} y1={l.source.y} x2={l.target.x} y2={l.target.y} className="kg-link-hit"
                      onMouseEnter={() => setHovered({ link: l.i })} onMouseLeave={() => setHovered(null)} />
                  )}
                </g>
              );
            })}
          </g>
          <g>
            {layout.simNodes.map((n) => {
              const on = isLit(n.id);
              const side = layout.labelled.get(n.id);
              const showLabel = lit ? lit.has(n.id) : !!side;
              return (
                <g key={n.id} transform={`translate(${n.x},${n.y})`}
                  className={`kg-node${on ? "" : " dim"}${pinned === n.id ? " pinned" : ""}`}
                  onMouseEnter={() => setHovered({ node: n.id })} onMouseLeave={() => setHovered(null)}
                  onClick={(e) => { e.stopPropagation(); setPinned(pinned === n.id ? null : n.id); }}>
                  <circle r={Math.max(n.r, 10)} className="kg-hit" />
                  <circle r={n.r} className={n.kind === "drug" ? "kg-drug" : "kg-cond"} />
                  {showLabel && (
                    <text x={side === "left" ? -n.r - 4 : n.r + 4} dy="0.35em" textAnchor={side === "left" ? "end" : "start"}
                      className="kg-label">{short(n.label)}</text>
                  )}
                </g>
              );
            })}
          </g>
        </svg>

        <aside className="kg-explain" aria-live="polite">
          {focusLink ? (
            <LinkExplain l={focusLink} windowDays={windowDays} />
          ) : focusNode ? (
            <NodeExplain node={layout.byId.get(focusNode)!} links={layout.simLinks} patients={patients}
              windowDays={windowDays} cases={casesFor?.(layout.byId.get(focusNode)!) ?? []} pinned={pinned === focusNode} />
          ) : (
            <HowToRead />
          )}
        </aside>
      </div>
    </div>
  );
}

function HowToRead() {
  return (
    <>
      <span className="eyebrow">How to read this</span>
      <p>Every drug and condition in the population is a circle. Lines show how they connect.</p>
      <ul className="kg-list">
        <li><b>Solid line:</b> people on the drug got the condition far more often than people not on it. A lead worth checking.</li>
        <li><b>Dashed line:</b> the drug was prescribed for the condition. It's a treatment, so it is never counted as a reaction.</li>
        <li><b>Faint line:</b> the two drugs are often taken together, so one can be mistaken for the other.</li>
      </ul>
      <p className="muted">Hover a circle or line to explain it. Tap a circle to pin it and jump to its cases.</p>
    </>
  );
}

function reactionSentence(l: SimLink, windowDays: number) {
  return `${l.n} of ${l.exposed ?? "?"} people on ${l.source.label} (${percent(l.rate_exposed ?? 0)}) got ${l.target.label}`
    + `${l.dated ? ` within ${windowDays} days of starting it` : ""}, compared with ${percent(l.rate_unexposed ?? 0)} of people not on it.`;
}

function LinkExplain({ l, windowDays }: { l: SimLink; windowDays: number }) {
  if (l.kind === "treats") {
    return (
      <>
        <span className="eyebrow">Prescribed for</span>
        <h3>{l.source.label} → {l.target.label}</h3>
        <p>{l.n} people were given {l.source.label} to treat {l.target.label}.</p>
        <p className="kg-tip">So if a case on {l.source.label} has {l.target.label}, the drug is probably the treatment, not the cause. These pairs are left out of the signals.</p>
      </>
    );
  }
  return (
    <>
      <span className="eyebrow">Possible reaction</span>
      <h3>{l.source.label} → {l.target.label}</h3>
      <p className="kg-big">{times(l.prr ?? null)} <span>as often as people not on it</span></p>
      <p>{reactionSentence(l, windowDays)}</p>
      <p className="kg-tip">Reviewing a case of {l.target.label} in someone on {l.source.label}? Look at this drug early, then check timing, dose changes and other explanations. A pattern is a lead, not proof.</p>
    </>
  );
}

function NodeExplain({ node, links, patients, windowDays, cases, pinned }: {
  node: SimNode; links: SimLink[]; patients: number; windowDays: number; cases: DeckCase[]; pinned: boolean;
}) {
  const mine = links.filter((l) => l.source.id === node.id || l.target.id === node.id);
  const reactions = mine.filter((l) => l.kind === "signal").sort((a, b) => (b.prr ?? 0) - (a.prr ?? 0));
  const treats = mine.filter((l) => l.kind === "treats").sort((a, b) => b.n - a.n);
  const together = mine.filter((l) => l.kind === "co_prescribed").sort((a, b) => b.n - a.n).slice(0, 4);
  const other = (l: SimLink) => (l.source.id === node.id ? l.target : l.source).label;
  const isDrug = node.kind === "drug";

  return (
    <>
      <span className="eyebrow">{isDrug ? "Drug" : "Condition"}{pinned ? " · pinned" : ""}</span>
      <h3>{node.label}</h3>
      <p className="muted">{isDrug ? "Taken by" : "Seen in"} {node.count} of {patients.toLocaleString()} patients.</p>

      {reactions.length > 0 && (
        <>
          <h4>{isDrug ? "Possible reactions" : "Drugs that may cause it"}</h4>
          <ul className="kg-list">
            {reactions.slice(0, 4).map((l) => (
              <li key={l.i}><b>{other(l)}</b>: {times(l.prr ?? null)} as often ({l.n} of {l.exposed} on the drug vs {percent(l.rate_unexposed ?? 0)} of others)</li>
            ))}
          </ul>
        </>
      )}
      {treats.length > 0 && (
        <>
          <h4>{isDrug ? "Prescribed for (not reactions)" : "Treated with (not causes)"}</h4>
          <p>{treats.slice(0, 5).map((l) => `${other(l)} (${l.n})`).join(", ")}</p>
        </>
      )}
      {together.length > 0 && (
        <>
          <h4>Often taken with</h4>
          <p>{together.map((l) => `${other(l)} (${l.n})`).join(", ")}</p>
        </>
      )}

      <p className="kg-tip">
        {reactions.length > 0
          ? isDrug
            ? `If a case on ${node.label} shows ${other(reactions[0])}, consider this drug early. Check timing (within ${windowDays} days) and rule out other causes.`
            : `Reviewing a case of ${node.label}? If the patient takes ${reactions.slice(0, 3).map(other).join(" or ")}, check ${reactions.length > 1 ? "those" : "it"} first.`
          : isDrug
            ? `Nothing in this population links ${node.label} to a condition beyond chance. Weigh the label and the timeline instead.`
            : `No drug stands out for ${node.label} in this population, so rely on the label, the timeline and the dechallenge.`}
      </p>

      {cases.length > 0 && (
        <>
          <h4>In your review deck</h4>
          <ul className="kg-cases">
            {cases.slice(0, 5).map((c) => <li key={c.id}><Link to={c.href}>{c.label}</Link></li>)}
          </ul>
          {cases.length > 5 && <p className="muted">and {cases.length - 5} more</p>}
        </>
      )}
      {!pinned && cases.length > 0 && <p className="muted kg-small">Tap the circle to pin this and open a case.</p>}
    </>
  );
}