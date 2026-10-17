import type { Candidate } from "../../types";
import EvidenceForDrug from "../evidence/EvidenceForDrug";
import RoleBadge from "../evidence/RoleBadge";

export default function CandidateCard({ candidate: c }: { candidate: Candidate }) {
  return (
    <article className="card">
      <div className="card-head">
        <strong>{c.name}</strong>
        <RoleBadge role={c.role} />
      </div>
      <div className="tally">
        <span className="pill for">{c.for.length} for</span>
        <span className="pill against">{c.against.length} against</span>
        <span className="pill unknown">{c.unknown.length} unknown</span>
      </div>
      <EvidenceForDrug candidate={c} />
    </article>
  );
}
