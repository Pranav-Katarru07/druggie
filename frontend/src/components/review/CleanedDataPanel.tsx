import type { ReactNode } from "react";
import { shortDrugName } from "../../data/drugName";
import type { CleanedData } from "../../types";

interface Column<T> {
  label: string;
  cell: (row: T) => ReactNode;
}

// "1778" characters -> "✓ 1.8k"; 0 -> "—"
const size = (n: number) => (n ? `✓ ${n >= 1000 ? `${(n / 1000).toFixed(1)}k` : n}` : "—");
const or = (v: ReactNode) => (v === null || v === undefined || v === "" ? "—" : v);
const flag = (ok: boolean, yes = "Yes", no = "No") => <span className={ok ? "flag ok" : "flag"}>{ok ? yes : no}</span>;

function Table<T>({ rows, columns, empty }: { rows: T[]; columns: Column<T>[]; empty: string }) {
  if (rows.length === 0) return <p className="data-empty">{empty}</p>;
  return (
    <div className="data-scroll">
      <table className="data-table">
        <thead><tr>{columns.map((c) => <th key={c.label}>{c.label}</th>)}</tr></thead>
        <tbody>
          {rows.map((r, i) => <tr key={i}>{columns.map((c) => <td key={c.label}>{c.cell(r)}</td>)}</tr>)}
        </tbody>
      </table>
    </div>
  );
}

function Section({ title, uses, note, children }: { title: string; uses: string; note: string; children: ReactNode }) {
  return (
    <section className="data-section">
      <h3 title={`Used by ${uses}`}>{title}</h3>
      <p className="data-note">{note}</p>
      {children}
    </section>
  );
}

// The cleaned tables for the case on the card, shown beside it once it's flipped
export default function CleanedDataPanel({ data }: { data?: CleanedData }) {
  if (!data) return <aside className="data-panel"><p className="data-empty">No cleaned data for this case.</p></aside>;
  return (
    <aside className="data-panel" aria-label="Cleaned data">

      <Section title="Reactions" uses="Q1–Q4, Q10" note="From conditions.csv. The end date only counts if it means the reaction actually went away.">
        <Table rows={data.reactions} empty="None." columns={[
          { label: "Reaction", cell: (r) => <>{r.reaction}{r.planted && <em className="planted"> planted</em>}</> },
          { label: "Start", cell: (r) => r.start },
          { label: "End", cell: (r) => or(r.end) },
          { label: "End usable", cell: (r) => (r.end_reliable ? flag(true) : <span className="flag" title={r.end_note ?? ""}>No: {r.end_note}</span>) },
          { label: "Lab tests", cell: (r) => or(r.lab_tests.join(", ")) },
        ]} />
      </Section>

      <Section title="Drug courses" uses="Q1–Q4, Q8" note="From medications.csv. Refills within 30 days merged into one course; code → active ingredient and class via RxNorm / RxClass.">
        <Table rows={data.drug_courses} empty="None." columns={[
          { label: "Drug", cell: (r) => shortDrugName(r.drug) },
          { label: "Ingredient", cell: (r) => or(r.ingredients) },
          { label: "Class", cell: (r) => or(r.class) },
          { label: "Strength", cell: (r) => or(r.strength) },
          { label: "Taken", cell: (r) => `${r.start} → ${r.stop ?? "ongoing"}` },
          { label: "Rx merged", cell: (r) => r.prescriptions_merged },
        ]} />
      </Section>

      <Section title="Label side-effect sections" uses="Q1" note="openFDA label. Only these sections count as a known side effect (size in characters).">
        <Table rows={data.label_side_effects} empty="None." columns={[
          { label: "Drug", cell: (r) => shortDrugName(r.drug) },
          { label: "Label", cell: (r) => (r.found ? flag(true, r.via ? `Yes (${r.via})` : "Yes") : flag(false, "", "Not found")) },
          { label: "Boxed warning", cell: (r) => size(r.boxed_warning) },
          { label: "Warnings", cell: (r) => size(r.warnings) },
          { label: "Adverse reactions", cell: (r) => size(r.adverse_reactions) },
        ]} />
      </Section>

      <Section title="Lab trend" uses="Q3" note="observations.csv tests that measure these reactions, 7 days before to 120 days after onset. Synthea has no normal ranges; these are typical adult limits.">
        <Table rows={data.labs} empty="No matching lab tests near onset." columns={[
          { label: "Test", cell: (r) => <>{r.test}{r.planted && <em className="planted"> planted</em>}</> },
          { label: "Day", cell: (r) => (r.day > 0 ? `+${r.day}` : r.day) },
          { label: "Value", cell: (r) => <span className={r.abnormal ? "abnormal" : undefined}>{r.value} {r.units}</span> },
          { label: "Normal", cell: (r) => r.normal },
        ]} />
      </Section>

      <Section title="Objective evidence" uses="Q10" note="An abnormal test from 7 days before to 30 days after onset.">
        <Table rows={data.objective_evidence} empty="None." columns={[
          { label: "Reaction", cell: (r) => r.reaction },
          { label: "Confirmed", cell: (r) => flag(r.found) },
          { label: "Evidence", cell: (r) => (r.evidence.length ? r.evidence.join("; ") : or(r.note)) },
        ]} />
      </Section>

      <Section title="Other courses of the same or similar drug" uses="Q4, Q8" note="Earlier or later courses sharing an ingredient (same drug) or an ATC class (same class).">
        <Table rows={data.re_exposures} empty="No other course of these drugs." columns={[
          { label: "Drug", cell: (r) => shortDrugName(r.drug) },
          { label: "Other course", cell: (r) => shortDrugName(r.other_course) },
          { label: "Match", cell: (r) => r.match },
          { label: "When", cell: (r) => `${r.when}: ${r.start} → ${r.stop ?? "ongoing"}` },
          { label: "Reaction then", cell: (r) => or(r.same_reaction_during.join(", ")) },
        ]} />
      </Section>

      <Section title="Drug allergies" uses="Q8" note="allergies.csv, medication entries, with the allergen's drug class.">
        <Table rows={data.drug_allergies} empty="No drug allergies recorded." columns={[
          { label: "Allergen", cell: (r) => `${r.allergen} (${r.type})` },
          { label: "Reaction", cell: (r) => or(r.reaction && `${r.reaction}${r.severity ? `, ${r.severity}` : ""}`) },
          { label: "Class", cell: (r) => or(r.class) },
          { label: "Matches a current drug", cell: (r) => or(r.matches.map((m) => `${shortDrugName(m.drug)} (${m.match})`).join(", ")) },
        ]} />
      </Section>
    </aside>
  );
}
