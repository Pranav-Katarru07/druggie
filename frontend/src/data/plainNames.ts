// Shorter, everyday names for the front of the card. The data keeps the full clinical names.
const NAMES: Record<string, string> = {
  "Essential hypertension": "High blood pressure",
  "Hyperlipidemia": "High cholesterol",
  "Hypertriglyceridemia": "High triglycerides",
  "Ischemic heart disease": "Heart disease",
  "Diabetes mellitus type 2": "Type 2 diabetes",
  "Metabolic syndrome X": "Metabolic syndrome",
  "Obstructive sleep apnea syndrome": "Sleep apnea",
  "Obesity (BMI 30+)": "Obesity",
  "Dependent drug abuse": "Drug dependence",
  "Misuses drugs": "Drug misuse",
  "Severe anxiety (panic)": "Severe anxiety",
  "Pulmonary emphysema": "Emphysema",
  "Perennial allergic rhinitis": "Hay fever",
  "Child attention deficit disorder": "ADHD",
  "Osteoarthritis of knee": "Knee arthritis",
  "Chronic intractable migraine without aura": "Chronic migraine",
  "Recurrent urinary tract infection": "Recurring UTIs",
  "Non-small cell lung cancer": "Lung cancer",
  "Acute non-ST segment elevation myocardial infarction": "Heart attack",
  "Acute ST segment elevation myocardial infarction": "Heart attack",
  "Pain in right upper quadrant of abdomen": "Pain under the right ribs",
};

export function plainName(name: string): string {
  const ckd = name.match(/^Chronic kidney disease stage (\d)$/);
  if (ckd) return `Kidney disease (stage ${ckd[1]})`;
  return NAMES[name] ?? name;
}

// Complications listed separately by Synthea ("Proteinuria due to type 2 diabetes mellitus") add noise on the card
export function isComplication(name: string): boolean {
  return / due to /i.test(name) || name === "Sleep disorder";
}

export function plainSmoking(status: string): string {
  if (/never/i.test(status)) return "Never";
  if (/ex-smoker|former/i.test(status)) return "Former";
  if (/daily|every day/i.test(status)) return "Daily";
  return status;
}
