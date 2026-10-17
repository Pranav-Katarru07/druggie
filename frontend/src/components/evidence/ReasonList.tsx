import type { Reason } from "../../types";

type Kind = "for" | "against" | "unknown";

export default function ReasonList({ kind, title, reasons }: { kind: Kind; title?: string; reasons: Reason[] }) {
  if (reasons.length === 0) return null;
  return (
    <div className="reason-group">
      {title && <h4 className={`reason-title ${kind}`}>{title}</h4>}
      <ul className={`reasons ${kind}`}>
        {reasons.map((r, i) => (
          <li key={i}>
            {r.text}
            {r.quote && (
              <blockquote>
                <span className="quote-source">{r.section}</span>
                “{r.quote}”
              </blockquote>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
