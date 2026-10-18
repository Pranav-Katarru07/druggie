// Shape of frontend/public/data.json, written by synthea_pipeline.py

// FAERS: how the reporter classed the drug. Synthea: "New" = started within 90 days before onset,
// "After" = started on or up to 30 days after onset (a likely treatment).
export type Role = "Suspect" | "Concomitant" | "New" | "Ongoing" | "After";

// One answered Naranjo question for one drug (synthea_pipeline.py QUESTIONS)
export interface Answer {
  number?: number; // Naranjo question number
  short?: string; // e.g. "Known side effect"
  question: string;
  answer: "yes" | "no" | "unknown";
  points: number;
  why: string;
}

export interface Candidate {
  name: string;
  role: Role;
  answers: Answer[];
  score: number;
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
  // Pulled from the label by synthea_pipeline.py: empty / null when the label doesn't state them plainly
  boxed_headline?: string | null; // e.g. "Pulmonary, hepatic and cardiac toxicity"
  serious_side_effects?: string[]; // "The following serious adverse reactions are described...: X, Y"
  common_side_effects?: string[]; // "The most common adverse reactions are a, b, c"
  boxed_warning?: string | null;
  warnings?: string | null;
  adverse_reactions?: string | null;
}

// Response from POST /api/suggest (server.py)
export interface CitedEvidence {
  id: string;
  drug: string;
  reaction: string;
  kind: "fact" | "answer";
  text: string;
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

// Cleaned tables for one case (synthea_pipeline.py clean_case); what the Naranjo questions read
export interface CleanedData {
  reactions: {
    reaction: string; search_term: string; code: string | null; start: string; end: string | null;
    end_reliable: boolean; end_note: string | null; lab_tests: string[]; planted: boolean;
  }[];
  drug_courses: {
    drug: string; ingredients: string | null; class: string | null; strength: string | null;
    start: string; stop: string | null; prescriptions_merged: number;
  }[];
  // Section sizes in characters; 0 = section missing from the label
  label_side_effects: { drug: string; found: boolean; via: string | null; boxed_warning: number; warnings: number; adverse_reactions: number }[];
  labs: { test: string; date: string; day: number; value: number; units: string; normal: string; abnormal: boolean; planted: boolean }[];
  objective_evidence: { reaction: string; found: boolean; evidence: string[]; note: string | null }[];
  re_exposures: {
    drug: string; other_course: string; match: "same drug" | "same class"; when: "before" | "after";
    start: string; stop: string | null; same_reaction_during: string[];
  }[];
  drug_allergies: {
    allergen: string; type: string; reaction: string | null; severity: string | null;
    since: string; class: string | null; matches: { drug: string; match: "same drug" | "same class" }[];
  }[];
}

// One case: a person + the problem(s) that began on one date + the drugs they were on.
// (Named Patient for history; Synthea cases share person_id when it's the same person.)
export interface Patient {
  id: string;
  person_id?: string;
  name?: string;
  age: string | null;
  sex: string;
  onset?: string; // Synthea only: date the condition(s) began
  reactions: string[];
  // Synthea only: what the patient reported or showed near onset (symptom findings, pain score, fever...)
  felt?: { text: string; planted: boolean }[];
  // Synthea only: who the patient is at onset (latest check-up in the year before, conditions already ongoing)
  details?: {
    race: string | null; ethnicity: string | null; marital: string | null; place: string | null;
    bmi: string | null; blood_pressure: string | null; smoking: string | null;
    existing_conditions: string[]; // oldest first
  };
  drugs: Drug[];
  assessment: ReactionAssessment[];
  cleaned?: CleanedData; // Synthea only
}
