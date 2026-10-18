import { useMemo } from "react";
import { Link } from "react-router";
import { buildCards, groupByProbableDrug } from "../components/review/reviewCards";
import { useDecisions } from "../components/review/useDecisions";
import { usePatientList } from "../data/patientsContext";
import "../components/review/Drugs.css";

// One card per drug: its name and how many cases it's the most likely cause of
export default function DrugsPage() {
  const patients = usePatientList();
  const groups = useMemo(() => groupByProbableDrug(buildCards(patients)), [patients]);
  const { decisions } = useDecisions();

  if (groups.length === 0) return <p className="empty">Nothing to review.</p>;

  return (
    <div className="drugs">
      <h1 className="drugs-title">Drugs</h1>
      <ul className="drug-grid">
        {groups.map((g) => {
          const done = g.cards.every((c) => decisions[c.key]); // fully reviewed cards fade
          return (
            <li key={g.key}>
              <Link to={`/review/${g.key}`} className={done ? "drug-card done" : "drug-card"}>
                <h2>{g.name}</h2>
                <span className="drug-card-count">{g.cards.length} {g.cards.length === 1 ? "case" : "cases"}</span>
              </Link>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
