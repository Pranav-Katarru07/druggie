import type { Drug } from "../../types";
import RoleBadge from "../evidence/RoleBadge";

export default function DrugLabel({ drug: d }: { drug: Drug }) {
  const sections: [string, string | null | undefined][] = [
    ["Boxed warning", d.boxed_warning],
    ["Warnings", d.warnings],
    ["Adverse reactions (side effects)", d.adverse_reactions],
  ];
  return (
    <article className="card">
      <div className="card-head">
        <strong>{d.name}</strong>
        <RoleBadge role={d.role} />
      </div>
      {d.indication && <p className="muted card-note">Taken for {d.indication.toLowerCase()}</p>}
      {d.started && <p className="muted card-note">Taken {d.started} → {d.stopped ?? "ongoing"}</p>}
      {d.label_via && <p className="muted card-note">Label found by {d.label_via}</p>}
      {!d.label_found ? (
        <p className="muted card-note">No label found for this drug name.</p>
      ) : (
        sections
          .filter(([, text]) => text)
          .map(([title, text]) => (
            <details key={title} className="label-section">
              <summary>{title}</summary>
              <p>{text}</p>
            </details>
          ))
      )}
    </article>
  );
}
