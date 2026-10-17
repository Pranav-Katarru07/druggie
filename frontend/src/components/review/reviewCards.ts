import type { Candidate, Drug, Patient } from "../../types";

// One card = one drug for one patient: "is this drug the cause?"
export interface ReviewCard {
  key: string;
  patient: Patient;
  drug: Drug;
  perReaction: { reaction: string; candidate: Candidate }[];
  indexInPatient: number;
}

export function buildCards(patients: Patient[]): ReviewCard[] {
  const cards: ReviewCard[] = [];
  for (const patient of patients) {
    const assessable = patient.assessment.filter((a) => a.assessable);
    if (assessable.length === 0) continue; // nothing clinical to judge
    patient.drugs.forEach((drug, i) => {
      const perReaction = assessable.flatMap((a) => {
        const candidate = a.drugs?.find((c) => c.name === drug.name);
        return candidate ? [{ reaction: a.reaction, candidate }] : [];
      });
      cards.push({ key: `${patient.id}::${drug.name}`, patient, drug, perReaction, indexInPatient: i });
    });
  }
  return cards;
}

export function cardStats(card: ReviewCard) {
  return {
    onLabel: card.perReaction.filter((r) => r.candidate.for.some((x) => x.quote)).length,
    forCount: card.perReaction.reduce((n, r) => n + r.candidate.for.length, 0),
    againstCount: card.perReaction.reduce((n, r) => n + r.candidate.against.length, 0),
  };
}
