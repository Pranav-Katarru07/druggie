import { Link } from "react-router";
import { day } from "../data/dates";
import { shortDrugName } from "../data/drugName";
import { caseName } from "../data/people";
import { usePatientList } from "../data/patientsContext";
import type { PairStat } from "./types";
import { percent, times, useInsights } from "./useInsights";
import "./insights.css";

// Card back, "Insights" page: what the wider population says about this case's drugs and symptoms.
export default function CaseInsight({ caseId }: { caseId: string }) {
  const state = useInsights();
  const patients = usePatientList();

  if (state.status === "loading") return <p className="muted">Loading insights…</p>;
  if (state.status === "missing") return <p className="muted">{state.message}</p>;

  const info = state.byCase.get(caseId);
  if (!info) return <p className="muted">This case isn't in the latest insights. Re-run <code>python -m analytics</code>.</p>;

  const { data } = state;
  const shown = info.pairs.filter((p) => p.n > 0).slice(0, 5);
  const unseen = info.pairs.filter((p) => p.n === 0);
  // A person can have several cases, so add the date the problem began
  const name = (id: string) => {
    const p = patients.find((x) => x.id === id);
    if (!p) return id;
    return p.onset ? `${caseName(p)}, ${day(p.onset)}` : caseName(p);
  };

  return (
    <div className="ci">
      <p className="plain-label">Compared with {data.counts.patients.toLocaleString()} patients</p>
      <div className="ci-head">
        <div>
          <span className="eyebrow">Group {info.cluster + 1} of {data.clusters.length}</span>
          <p className="ci-group">{info.cluster_label}</p>
        </div>
        <span className="ci-priority" title="Higher = swipe sooner. Based on population signals and how unusual the case is.">
          <b>{info.priority}</b> priority
        </span>
      </div>
      {info.unusual > 1.5 && <p className="ci-note">Unusual for its group: its drugs and conditions differ from most patients in it.</p>}

      <h3 className="ci-h">Drug → symptom in the population</h3>
      {shown.length === 0 && <p className="muted ci-small">None of this case's drug and symptom pairs appear in the population.</p>}
      <ul className="ci-pairs">
        {shown.map((p) => <PairRow key={`${p.drug}|${p.ingredient}|${p.condition}`} p={p} windowDays={data.params.window_days} />)}
      </ul>
      {unseen.length > 0 && (
        <p className="muted ci-small">
          Not seen in anyone on the drug: {unseen.slice(0, 4).map((p) => `${p.ingredient} → ${p.condition}`).join("; ")}
          {unseen.length > 4 && ` and ${unseen.length - 4} more`}.
        </p>
      )}

      {info.similar.length > 0 && (
        <>
          <h3 className="ci-h">Similar cases in the deck</h3>
          <ul className="ci-similar">
            {info.similar.map((s) => {
              const p = patients.find((x) => x.id === s.id);
              return (
                <li key={s.id}>
                  <Link to={`/patients/${p?.person_id ?? s.id}`}>{name(s.id)}</Link>
                  <span className="muted">{Math.round(s.similarity * 100)}% alike</span>
                </li>
              );
            })}
          </ul>
        </>
      )}

      <p className="back-callout">
        Population patterns show what happens together more often than expected, not what caused it.
        {" "}<Link to="/insights">See all groups and signals</Link>
      </p>
    </div>
  );
}

function PairRow({ p, windowDays }: { p: PairStat; windowDays: number }) {
  const max = Math.max(p.rate_exposed, p.rate_unexposed, 0.0001);
  const drug = shortDrugName(p.drug);
  return (
    <li className="ci-pair">
      <div className="ci-pair-head">
        <strong>{drug} → {p.condition}</strong>
        {p.signal ? <span className="ci-flag">Signal</span> : null}
      </div>
      <div className="ci-bars" aria-label={`${percent(p.rate_exposed)} of people on ${drug} versus ${percent(p.rate_unexposed)} of people not on it`}>
        <span className="ci-bar-label">On {drug}</span>
        <span className="ci-bar"><i style={{ width: `${(p.rate_exposed / max) * 100}%` }} /></span>
        <span className="ci-bar-value">{percent(p.rate_exposed)}</span>
        <span className="ci-bar-label">Not on it</span>
        <span className="ci-bar"><i className="off" style={{ width: `${(p.rate_unexposed / max) * 100}%` }} /></span>
        <span className="ci-bar-value">{percent(p.rate_unexposed)}</span>
      </div>
      <p className="ci-small muted">
        {p.n} of {p.exposed} people on it got this
        {p.dated > 0 && ` (${p.dated} within ${windowDays} days of starting it)`}
        {p.prr !== null && `, ${times(p.prr)} as often as people not on it`}.
        {p.treats > 0 && ` It was prescribed for this in ${p.treats} people, so those don't count.`}
      </p>
    </li>
  );
}
