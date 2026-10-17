import { NavLink } from "react-router";
import type { Patient } from "../../types";

export default function PatientList({ patients }: { patients: Patient[] }) {
  if (patients.length === 0) return <p className="muted pad">No matches.</p>;
  return (
    <ul className="patient-list">
      {patients.map((p) => (
        <li key={p.id}>
          <NavLink to={`/browse/${p.id}`} className="patient-item">
            <span className="patient-item-title">Patient {p.id}</span>
            <span className="muted">
              {p.sex}, {p.age ? `${p.age} yrs` : "age unknown"} · {p.drugs.length} drug{p.drugs.length === 1 ? "" : "s"}
            </span>
            <span className="chips">
              {p.reactions.map((r) => <span key={r} className="chip reaction-chip">{r}</span>)}
            </span>
          </NavLink>
        </li>
      ))}
    </ul>
  );
}
