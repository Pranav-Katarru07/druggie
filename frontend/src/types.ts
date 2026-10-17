// Shape of frontend/public/data.json, written by extractData.py

// FAERS: how the reporter classed the drug. Synthea: "New" = started within 90 days of onset.
export type Role = "Suspect" | "Concomitant" | "New" | "Ongoing";

export interface Reason {
  text: string;
  section?: string; // label section the quote came from
  quote?: string;
}

export interface Candidate {
  name: string;
  role: Role;
  for: Reason[];
  against: Reason[];
  unknown: Reason[];
}

export interface ReactionAssessment {
  reaction: string;
  assessable: boolean;
  note?: string; // why it was skipped, when not assessable
  drugs?: Candidate[];
}

export interface Drug {
  name: string;
  role: Role;
  indication: string | null;
  label_found: boolean;
  label_via?: string | null; // set when the label was found by another name than the reported one
  started?: string; // Synthea only: course start/stop dates (YYYY-MM-DD)
  stopped?: string | null;
  boxed_warning?: string | null;
  warnings?: string | null;
  adverse_reactions?: string | null;
}

// Response from POST /api/suggest (server.py)
export interface CitedEvidence extends Reason {
  id: string;
  drug: string;
  reaction: string;
  kind: "for" | "against" | "unknown";
}

export interface Suggestion {
  most_likely: string | null;
  confidence: "low" | "medium" | "high";
  summary: string;
  drugs: {
    name: string;
    assessment: string;
    explains?: string[];
    reasons: { text: string; evidence: CitedEvidence[] }[];
  }[];
  unexplained_reactions?: string[];
  missing_information: string[];
  model: string;
}

export interface Patient {
  id: string;
  age: string | null;
  sex: string;
  onset?: string; // Synthea only: date the condition(s) began
  reactions: string[];
  drugs: Drug[];
  assessment: ReactionAssessment[];
}
