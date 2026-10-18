import { shortDrugName } from "../../data/drugName";
import type { Person } from "../../data/people";
import type { Patient } from "../../types";
import AnswerList from "../evidence/AnswerList";
import RoleBadge from "../evidence/RoleBadge";

export default function PersonDetail({ person }: { person: Person }) {
  return (
    <div className="person">
      <h2>{person.name}</h2>
      <p className="muted person-meta">{person.sex}{person.age && `, ${person.age}`}</p>
      {person.cases.map((c) => <CaseBlock key={c.id} c={c} />)}
    </div>
  );
}

function CaseBlock({ c }: { c: Patient }) {
  return (
    <section className="case">
      <h3>
        {c.reactions.join(", ")}
        {c.onset && <span className="muted"> · {c.onset}</span>}
      </h3>
      <ul className="drug-rows">
        {c.drugs.map((d) => {
          const candidates = c.assessment.flatMap((a) => a.drugs?.filter((x) => x.name === d.name) ?? []);
          const answers = candidates.flatMap((x) => x.answers);
          const score = candidates.length ? Math.max(...candidates.map((x) => x.score)) : null;
          return (
            <li key={d.name}>
              <details className="drug-row">
                <summary>
                  <span className="drug-row-name">{shortDrugName(d.name)}</span>
                  <span className="drug-row-tags">
                    {answers.length > 0 && score !== null && <span className="muted">Score {score}</span>}
                    <RoleBadge role={d.role} />
                  </span>
                </summary>
                <div className="drug-row-body">
                  <p className="muted drug-row-dates">
                    {d.name}
                    {d.started && <><br />Taken {d.started} → {d.stopped ?? "ongoing"}</>}
                    {d.indication && <><br />Prescribed for {d.indication.toLowerCase()}</>}
                  </p>
                  <AnswerList answers={answers} showZero />
                </div>
              </details>
            </li>
          );
        })}
      </ul>
    </section>
  );
}
