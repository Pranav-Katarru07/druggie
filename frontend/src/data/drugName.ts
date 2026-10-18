// "1 ML medroxyPROGESTERone acetate 150 MG/ML Injection" -> "Medroxyprogesterone acetate"
// "24 HR metoprolol succinate 100 MG Extended Release Oral Tablet" -> "Metoprolol succinate"
// "Acetaminophen 325 MG / Oxycodone Hydrochloride 10 MG Oral Tablet [Percocet]" -> "Percocet"
// FAERS names ("BONIVA") pass through unchanged apart from casing.
export function shortDrugName(description: string): string {
  const brand = description.match(/\[([^\]]+)\]\s*$/)?.[1];
  if (brand) return brand;

  // Leading package amounts ("1 ML", "24 HR") and FDA application numbers ("NDA020800")
  const withoutAmount = description.replace(/^((NDA\d+|\d+(\.\d+)?\s*(ML|HR|DAY|ACTUAT|MG))\s+)+/i, "");
  const ingredients = withoutAmount
    .split(" / ")
    .map((part) => part.split(/\s\d/)[0].trim()) // drop everything from the first dose number on
    .filter(Boolean);
  const name = ingredients.join(" + ") || description;
  return name.charAt(0).toUpperCase() + name.slice(1).toLowerCase();
}
