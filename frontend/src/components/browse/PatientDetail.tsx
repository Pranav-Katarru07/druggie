import { useState } from "react";
import type { Patient } from "../../types";
import AiSuggestion from "../ai/AiSuggestion";
import CandidateCard from "./CandidateCard";
import DrugLabel from "./DrugLabel";

export default function PatientDetail({ patient }: { patient: Patient }) {
  const [tab, setTab] = useState<"causes" | "drugs">("causes");
  const assessable = patient.assessment.some((a) => a.assessable);

  return (
    <div className="detail-inner">
      <div className="detail-header">
        <h2>Patient {patient.id}</h2>
        <span className="muted">
          {patient.sex}, {patient.age ? `${patient.age} yrs` : "age unknown"}
          {patient.onset && ` · began ${patient.onset}`}
        </span>
      </div>

      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === "causes"} className={tab === "causes" ? "tab active" : "tab"} onClick={() => setTab("causes")}>
          Possible causes
        </button>
        <button role="tab" aria-selected={tab === "drugs"} className={tab === "drugs" ? "tab active" : "tab"} onClick={() => setTab("drugs")}>
          Drugs and labels ({patient.drugs.length})
        </button>
      </div>

      {tab === "causes" ? (
        <>
          {assessable && (
            <div className="detail-ai">
              <AiSuggestion patientId={patient.id} />
            </div>
          )}
          {patient.assessment.map((a) => (
            <section key={a.reaction} className="reaction">
              <h3>{a.reaction}</h3>
              {a.assessable ? (
                <div className="card-grid">
                  {a.drugs!.map((c) => <CandidateCard key={c.name} candidate={c} />)}
                </div>
              ) : (
                <p className="muted">{a.note}</p>
              )}
            </section>
          ))}
        </>
      ) : (
        <div className="card-grid labels">
          {patient.drugs.map((d) => <DrugLabel key={d.name} drug={d} />)}
        </div>
      )}
    </div>
  );
}
