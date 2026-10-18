import { shortDrugName } from "../../data/drugName";
import type { Candidate, Drug, Patient } from "../../types";

export interface RankedDrug {
  drug: Drug;
  reaction: string; // the symptom this drug scores highest on
  candidate: Candidate;
  score: number;
}

// One card = one case (a patient and the symptoms that began together)
export interface ReviewCard {
  key: string;
  patient: Patient;
  ranked: RankedDrug[]; // highest score first; most recently started first when scores tie
  answered: boolean; // at least one question has been computed for this case
  clearTop: boolean; // one drug scores strictly higher than the rest
}

function rank(patient: Patient): RankedDrug[] {
  const assessable = patient.assessment.filter((a) => a.assessable);
  const ranked = patient.drugs.flatMap((drug) => {
    const options = assessable.flatMap((a) => {
      const candidate = a.drugs?.find((c) => c.name === drug.name);
      return candidate ? [{ reaction: a.reaction, candidate }] : [];
    });
    if (options.length === 0) return [];
    // For a case with several symptoms, use the symptom this drug scores highest on
    const best = options.reduce((x, y) => (y.candidate.score > x.candidate.score ? y : x));
    return [{ drug, reaction: best.reaction, candidate: best.candidate, score: best.candidate.score }];
  });
  return ranked.sort((a, b) => b.score - a.score || (b.drug.started ?? "").localeCompare(a.drug.started ?? ""));
}

// The drug a case is filed under on the Drugs page
export interface ProbableDrug {
  key: string; // URL-safe, e.g. "norethindrone"
  name: string; // active ingredient(s), so brands of the same drug land together
  drugClass: string | null;
}

// For now: the top of the rule-based ranking (with no questions scored yet, that's the most recently
// started drug). This is the one place to swap in the AI's pick later.
export function probableDrug(card: ReviewCard): ProbableDrug {
  const top = card.ranked[0].drug;
  const course = card.patient.cleaned?.drug_courses.find((d) => d.drug === top.name);
  const name = course?.ingredients ?? shortDrugName(top.name);
  return {
    key: name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, ""),
    name: name.charAt(0).toUpperCase() + name.slice(1),
    drugClass: course?.class ?? null,
  };
}

export interface DrugGroup extends ProbableDrug {
  cards: ReviewCard[];
}

// Most cases first, then by name
export function groupByProbableDrug(cards: ReviewCard[]): DrugGroup[] {
  const groups = new Map<string, DrugGroup>();
  for (const card of cards) {
    const drug = probableDrug(card);
    const group = groups.get(drug.key) ?? { ...drug, cards: [] };
    group.cards.push(card);
    groups.set(drug.key, group);
  }
  return [...groups.values()].sort((a, b) => b.cards.length - a.cards.length || a.name.localeCompare(b.name));
}

export function buildCards(patients: Patient[]): ReviewCard[] {
  return patients
    .filter((p) => p.assessment.some((a) => a.assessable))
    .map((patient) => {
      const ranked = rank(patient);
      const answered = ranked.some((r) => r.candidate.answers.length > 0);
      const clearTop = answered && (ranked.length === 1 || ranked[0].score > ranked[1].score);
      return { key: patient.id, patient, ranked, answered, clearTop };
    })
    .filter((c) => c.ranked.length > 0);
}
