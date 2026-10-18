import { useMemo, useState } from "react";
import type { CaseInsight, Cluster, Point } from "./types";

const W = 640;
const H = 400;
const PAD = 28;

type Hover = { x: number; y: number; title: string; lines: string[] } | null;

// PCA map: every population patient is a grey dot, placed so that similar patients sit close together.
// Selecting a group darkens its dots; the app's cases are ringed. Group numbers sit at each group's centre.
export default function ClusterMap({ points, cases, clusters, selected, onSelect, highlightCase, caseName }: {
  points: Point[];
  cases: CaseInsight[];
  clusters: Cluster[];
  selected: number | null;
  onSelect: (cluster: number | null) => void;
  highlightCase?: string;
  caseName?: (id: string) => string;
}) {
  const [hover, setHover] = useState<Hover>(null);

  const scale = useMemo(() => {
    const all = [...points, ...cases];
    const xs = all.map((p) => p.x);
    const ys = all.map((p) => p.y);
    const [x0, x1] = [Math.min(...xs), Math.max(...xs)];
    const [y0, y1] = [Math.min(...ys), Math.max(...ys)];
    const sx = (v: number) => PAD + ((v - x0) / (x1 - x0 || 1)) * (W - 2 * PAD);
    const sy = (v: number) => H - PAD - ((v - y0) / (y1 - y0 || 1)) * (H - 2 * PAD);
    return { sx, sy };
  }, [points, cases]);

  const centres = useMemo(
    () =>
      clusters.map((c) => {
        const mine = points.filter((p) => p.cluster === c.id);
        const x = mine.reduce((s, p) => s + scale.sx(p.x), 0) / (mine.length || 1);
        const y = mine.reduce((s, p) => s + scale.sy(p.y), 0) / (mine.length || 1);
        return { id: c.id, x, y };
      }),
    [clusters, points, scale],
  );

  const show = (e: React.MouseEvent, title: string, lines: string[]) => {
    const box = (e.currentTarget.closest(".cmap") ?? e.currentTarget).getBoundingClientRect();
    setHover({ x: e.clientX - box.left, y: e.clientY - box.top, title, lines });
  };

  return (
    <div className="cmap">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label="Map of patients grouped by similar drugs and conditions"
        onMouseLeave={() => setHover(null)} onClick={() => onSelect(null)}>
        <rect x={0} y={0} width={W} height={H} rx={16} className="cmap-bg" />

        {points.map((p) => {
          const on = selected === null || selected === p.cluster;
          return (
            <circle key={p.id} cx={scale.sx(p.x)} cy={scale.sy(p.y)} r={4}
              className={selected === p.cluster ? "cmap-dot picked" : on ? "cmap-dot" : "cmap-dot faded"}
              onMouseEnter={(e) => show(e, `Group ${p.cluster + 1}`, [
                clusters[p.cluster]?.label ?? "",
                ...(p.trial ? [p.trial] : []),
                p.signals ? `${p.signals} drug→condition signal${p.signals > 1 ? "s" : ""}` : "",
              ].filter(Boolean))}
              onClick={(e) => { e.stopPropagation(); onSelect(p.cluster === selected ? null : p.cluster); }} />
          );
        })}

        {centres.map((c) => (
          <g key={c.id} className="cmap-centre" transform={`translate(${c.x},${c.y})`}
            onClick={(e) => { e.stopPropagation(); onSelect(c.id === selected ? null : c.id); }}>
            <circle r={11} className={selected === c.id ? "picked" : ""} />
            <text dy="0.35em">{c.id + 1}</text>
          </g>
        ))}

        {cases.map((c) => {
          const hl = c.id === highlightCase;
          return (
            <g key={c.id} transform={`translate(${scale.sx(c.x)},${scale.sy(c.y)})`}
              onMouseEnter={(e) => show(e, caseName?.(c.id) ?? `Case ${c.id}`, [
                `Group ${c.cluster + 1}: ${c.cluster_label}`,
                `Priority ${c.priority}/100`,
              ])}
              onClick={(e) => e.stopPropagation()}>
              <circle r={12} className="cmap-hit" />
              <circle r={hl ? 7 : 5.5} className={hl ? "cmap-case current" : "cmap-case"} />
            </g>
          );
        })}
      </svg>

      {hover && (
        <div className="cmap-tip" style={{ left: hover.x, top: hover.y }} role="tooltip">
          <strong>{hover.title}</strong>
          {hover.lines.map((l) => <span key={l}>{l}</span>)}
        </div>
      )}

      <div className="cmap-key" aria-hidden>
        <span><i className="key-dot" /> Patient in the population</span>
        <span><i className="key-ring" /> Case in the review deck</span>
      </div>
    </div>
  );
}
