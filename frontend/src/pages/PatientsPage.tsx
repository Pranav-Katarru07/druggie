import { useEffect, useMemo, useRef } from "react";
import { logView } from "../data/logView";
import { NavLink, Navigate, useParams } from "react-router";
import PersonDetail from "../components/patients/PersonDetail";
import { usePatientList } from "../data/patientsContext";
import { groupPeople } from "../data/people";
import "../components/patients/Patients.css";

export default function PatientsPage() {
  const cases = usePatientList();
  const people = useMemo(() => groupPeople(cases), [cases]);
  const { personId } = useParams();

  // Print the person's cases in the server terminal when opened (ref skips StrictMode's double run)
  const lastLogged = useRef<string | null>(null);
  useEffect(() => {
    if (personId && lastLogged.current !== personId) {
      lastLogged.current = personId;
      logView({ event: "Opened in Patients", person_id: personId });
    }
  }, [personId]);

  if (!personId && people.length > 0) return <Navigate to={`/patients/${people[0].id}`} replace />;
  const selected = people.find((p) => p.id === personId);

  return (
    <div className="patients">
      <ul className="people">
        {people.map((p) => (
          <li key={p.id}>
            <NavLink to={`/patients/${p.id}`} className="person-link">
              <span>{p.name}</span>
              <span className="muted">{p.cases.length}</span>
            </NavLink>
          </li>
        ))}
      </ul>
      <div className="person-pane">
        {selected ? <PersonDetail key={selected.id} person={selected} /> : <p className="empty">Not found.</p>}
      </div>
    </div>
  );
}
