import type { Candidate } from "../../types";
import ReasonList from "./ReasonList";

// The +/–/? reasons for one drug and one reaction
export default function EvidenceForDrug({ candidate }: { candidate: Candidate }) {
  return (
    <>
      <ReasonList kind="for" title="Could be a cause because" reasons={candidate.for} />
      <ReasonList kind="against" title="Points against" reasons={candidate.against} />
      {candidate.unknown.length > 0 && (
        <details className="missing">
          <summary>Missing information ({candidate.unknown.length})</summary>
          <ReasonList kind="unknown" reasons={candidate.unknown} />
        </details>
      )}
    </>
  );
}
