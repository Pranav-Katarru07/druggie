import { useMemo, useState } from "react";
import { Navigate, useParams } from "react-router";
import PatientDetail from "../components/browse/PatientDetail";
import PatientList from "../components/browse/PatientList";
import { usePatientList } from "../data/patientsContext";
import "../components/browse/Browse.css";

export default function BrowsePage() {
  const patients = usePatientList();
  const { patientId } = useParams();
  const [query, setQuery] = useState("");

  // Search across patient id, reactions and drug names
  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return patients;
    return patients.filter((p) =>
      [p.id, ...p.reactions, ...p.drugs.map((d) => d.name)].some((s) => s.toLowerCase().includes(q)),
    );
  }, [patients, query]);

  // /browse with no patient picked: open the first one
  if (!patientId && patients.length > 0) return <Navigate to={`/browse/${patients[0].id}`} replace />;
  const selected = patients.find((p) => p.id === patientId);

  return (
    <div className="browse-page">
      <aside className="browse-sidebar">
        <input
          className="search"
          type="search"
          placeholder="Search patient, reaction or drug"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <PatientList patients={filtered} />
      </aside>
      <section className="browse-detail">
        {selected ? <PatientDetail key={selected.id} patient={selected} /> : <p className="empty">Patient not found.</p>}
      </section>
    </div>
  );
}
