import { useMemo, useState } from "react";
import { Link } from "react-router";
import { buildCards, groupByProbableDrug } from "../components/review/reviewCards";
import { caseName } from "../data/people";
import { usePatientList } from "../data/patientsContext";
import ClusterMap from "../insights/ClusterMap";
import KnowledgeGraph, { type DeckCase } from "../insights/KnowledgeGraph";
import type { GraphNode } from "../insights/types";
import { percent, times, useInsights } from "../insights/useInsights";
import "../insights/insights.css";

// Population view: groups of similar patients (PCA + k-means), drug→condition signals,
// a knowledge graph, and which review cards to swipe first.
export default function InsightsPage() {
  const state = useInsights();
  const patients = usePatientList();
  const [selected, setSelected] = useState<number | null>(null);
  const [allSignals, setAllSignals] = useState(false);

  // case id -> the review deck it's in (decks are grouped by most likely drug)
  const deckOf = useMemo(() => {
    const map = new Map<string, string>();
    for (const g of groupByProbableDrug(buildCards(patients))) for (const c of g.cards) map.set(c.key, g.key);
    return map;
  }, [patients]);
  const nameOf = (id: string) => {
    const p = patients.find((x) => x.id === id);
    return p ? caseName(p) : `Case ${id}`;
  };

  // Review cases that involve a graph node: the drug is one of the case's drugs, or the condition is one of its symptoms
  const casesFor = (node: GraphNode): DeckCase[] => {
    if (state.status !== "ready") return [];
    return state.data.cases
      .filter((c) => c.pairs.some((p) => (node.kind === "drug" ? p.ingredient === node.label : p.condition === node.label)))
      .map((c) => ({ id: c.id, label: nameOf(c.id), href: deckOf.has(c.id) ? `/review/${deckOf.get(c.id)}` : `/patients/${c.person_id}` }));
  };

  if (state.status === "loading") return <p className="empty">Loading insights…</p>;
  if (state.status === "missing") return <p className="empty">{state.message}</p>;
  const { data } = state;

  const first = [...data.cases].sort((a, b) => b.priority - a.priority).slice(0, 6);
  const signals = data.signals.filter((s) => s.signal);
  const table = allSignals ? data.signals.slice(0, 60) : signals.slice(0, 15);
  const group = selected === null ? null : data.clusters[selected];
  const [ax, ay] = data.axes;

  return (
    <div className="insights">
      <header className="ins-head">
        <h1 className="drugs-title">Insights</h1>
        <p className="muted">
          Patterns across {data.counts.patients.toLocaleString()} patients ({data.source}), used to decide what to review first.
          They show what happens together, not what caused it.
        </p>
        <dl className="ins-stats">
          <div><dt>Patients</dt><dd>{data.counts.patients.toLocaleString()}</dd></div>
          <div><dt>Groups</dt><dd>{data.clusters.length}</dd></div>
          <div><dt>Signals</dt><dd>{data.counts.signals}</dd></div>
          <div><dt>Cases in deck</dt><dd>{data.counts.cases}</dd></div>
        </dl>
      </header>

      <section className="ins-card ins-first">
        <h2>Swipe these first</h2>
        <ol className="ins-first-list">
          {first.map((c) => {
            const deck = deckOf.get(c.id);
            const top = c.pairs.find((p) => p.signal) ?? c.pairs.find((p) => p.n > 0);
            return (
              <li key={c.id}>
                <span className="ins-prio">{c.priority}</span>
                <div>
                  {deck ? <Link to={`/review/${deck}`}>{nameOf(c.id)}</Link> : <strong>{nameOf(c.id)}</strong>}
                  <span className="muted">
                    {top ? `${top.ingredient} → ${top.condition}: ${top.n} of ${top.exposed} on it (${times(top.prr)})` : "No population signal"}
                  </span>
                </div>
              </li>
            );
          })}
        </ol>
      </section>

      <section className="ins-card">
        <h2>Groups of similar patients</h2>
        <p className="muted ins-sub">
          Each dot is a patient, placed by their drugs and conditions (PCA), so similar patients sit close together.
          {ax && ` Left to right mostly reflects ${ax.top.slice(0, 3).map((t) => t.feature).join(", ")}`}
          {ay && `; bottom to top, ${ay.top.slice(0, 3).map((t) => t.feature).join(", ")}.`}
          {" "}Tap a group to highlight it.
        </p>
        <div className="ins-map">
          <ClusterMap points={data.points} cases={data.cases} clusters={data.clusters}
            selected={selected} onSelect={setSelected} caseName={nameOf} />
          <ul className="ins-groups">
            {data.clusters.map((c) => (
              <li key={c.id}>
                <button type="button" className={selected === c.id ? "ins-group picked" : "ins-group"}
                  onClick={() => setSelected(selected === c.id ? null : c.id)} aria-pressed={selected === c.id}>
                  <span className="ins-group-n">{c.id + 1}</span>
                  <span>
                    <strong>{c.label}</strong>
                    <span className="muted">{c.size} patients</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        </div>
        {group && (
          <table className="ins-table">
            <caption>What makes group {group.id + 1} different</caption>
            <thead><tr><th>Drug or condition</th><th>In this group</th><th>Everyone</th></tr></thead>
            <tbody>
              {group.features.map((f) => (
                <tr key={f.feature}>
                  <td>{f.feature} <span className="muted">({f.kind === "drug" ? "drug" : "condition"})</span></td>
                  <td>{percent(f.share)}</td>
                  <td>{percent(f.overall)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="ins-card">
        <h2>Knowledge graph</h2>
        <p className="muted ins-sub">
          How drugs and conditions connect across the population. It helps a reviewer see, before deciding, which drugs
          are linked to a symptom, which drugs are just its treatment, and which drugs travel together and get confused.
        </p>
        <KnowledgeGraph nodes={data.graph.nodes} links={data.graph.links} patients={data.counts.patients}
          windowDays={data.params.window_days} casesFor={casesFor} />
      </section>

      <section className="ins-card">
        <div className="ins-row">
          <h2>Drug → condition signals</h2>
          <button type="button" className="text-button" onClick={() => setAllSignals(!allSignals)}>
            {allSignals ? "Signals only" : "Show weaker pairs too"}
          </button>
        </div>
        <p className="muted ins-sub">
          Pairs where people on a drug got a condition at least twice as often as people not on it
          (at least {data.params.min_signal_n} people, chi-square ≥ 4).
          {` With dates, only conditions starting within ${data.params.window_days} days after the drug count.`}
        </p>
        {table.length === 0 ? (
          <p className="muted">No pairs pass yet. More patients, or dated data, will help.</p>
        ) : (
          <div className="ins-scroll">
            <table className="ins-table">
              <thead>
                <tr><th>Drug</th><th>Condition</th><th>On drug</th><th>Not on drug</th><th>Times as often</th><th>People</th></tr>
              </thead>
              <tbody>
                {table.map((s) => (
                  <tr key={`${s.drug}|${s.condition}`} className={s.signal ? "" : "weak"}>
                    <td>{s.drug}</td>
                    <td>{s.condition}</td>
                    <td>{percent(s.rate_exposed)}</td>
                    <td>{percent(s.rate_unexposed)}</td>
                    <td>{times(s.prr)}{s.signal && <span className="ci-flag">Signal</span>}</td>
                    <td>{s.n} of {s.exposed}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <section className="ins-foot muted">
        <h2>Read with care</h2>
        <ul>{data.caveats.map((c) => <li key={c}>{c}</li>)}</ul>
        <p>Generated {new Date(data.generated_at).toLocaleString()}.</p>
      </section>
    </div>
  );
}