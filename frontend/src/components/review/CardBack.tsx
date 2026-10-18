import { useState } from "react";
import { day } from "../../data/dates";
import { shortDrugName } from "../../data/drugName";
import type { Answer } from "../../types";
import AiSuggestion from "../ai/AiSuggestion";
import CleanedDataPanel from "./CleanedDataPanel";
import type { RankedDrug, ReviewCard } from "./reviewCards";

const PAGES = ["Drug", "Reasons", "Data"];
const LABEL_TEXT_CAP = 1500; // extractData.py MAX_TEXT: label sections are cut to this length
const ANSWER = { yes: "Yes", no: "No", unknown: "Don't know" };

// Naranjo categories: ≥9 definite, 5–8 probable, 1–4 possible, ≤0 doubtful
function category(score: number) {
  return score >= 9 ? "definite" : score >= 5 ? "probable" : score >= 1 ? "possible" : "doubtful";
}

const points = (n: number) => (n > 0 ? `+${n}` : `${n}`);

// Back: the drug, in pages. It opens up to full size once the flip finishes.
export default function CardBack({ card, onFlipBack }: { card: ReviewCard; onFlipBack: () => void }) {
  const [page, setPage] = useState(0);
  const [top, ...rest] = card.ranked;

  return (
    <div className="back">
      <div className="back-bar">
        <div className="pages" role="tablist" aria-label="Pages">
          {PAGES.map((p, i) => (
            <button key={p} type="button" role="tab" aria-selected={page === i}
              className={page === i ? "page-tab active" : "page-tab"} onClick={() => setPage(i)}>
              {p}
            </button>
          ))}
        </div>
        <button type="button" className="text-button" onClick={onFlipBack}>Close</button>
      </div>

      <div className="back-scroll" key={page}>
        {page === 0 && <DrugPage top={top} />}
        {page === 1 && <ReasonsPage card={card} top={top} rest={rest} />}
        {page === 2 && <CleanedDataPanel data={card.patient.cleaned} />}
      </div>
    </div>
  );
}

const LABEL_SECTIONS = [
  ["boxed_warning", "Boxed warning"],
  ["warnings", "Warnings"],
  ["adverse_reactions", "Adverse reactions"],
] as const;

// Page 1: the most likely drug, its side effects, and why it's the most likely
function DrugPage({ top }: { top: RankedDrug }) {
  const { drug } = top;
  const sections = LABEL_SECTIONS.filter(([key]) => drug[key]);
  const onLabel = top.candidate.answers.find((a) => a.number === 1 && a.answer === "yes");
  // The label quote is already shown under side effects, so don't repeat it here
  const scored = top.candidate.answers.filter((a) => a.points > 0)
    .map((a) => (a === onLabel ? { ...a, why: "Its label lists this reaction (quoted above)." } : a));
  const serious = drug.serious_side_effects ?? [];
  const common = drug.common_side_effects ?? [];
  const summarised = !!drug.boxed_headline || serious.length > 0 || common.length > 0;

  return (
    <>
      <p className="plain-label">Most likely cause</p>
      <h2 className="top-name">{shortDrugName(drug.name)}</h2>
      <p className="drug-detail">
        Score {top.score} ({category(top.score)})
        {drug.started && <> · taken {day(drug.started)} to {drug.stopped ? day(drug.stopped) : "now"}</>}
        {drug.indication && <> · for {drug.indication.toLowerCase()}</>}
      </p>

      <h3 className="plain-h">Side effects</h3>
      {!drug.label_found ? (
        <p className="drug-detail">No label found for this drug.</p>
      ) : (
        <>
          {drug.boxed_headline && (
            <div className="boxed">
              <span>Boxed warning</span>
              <strong>{drug.boxed_headline}</strong>
            </div>
          )}
          {onLabel && (
            <div className="matches">
              <span>Matches this patient</span>
              <p>{onLabel.why.replace(/^Its label \([^)]*\):\s*/, "")}</p>
            </div>
          )}
          {serious.length > 0 && <EffectList title="Serious" items={serious} />}
          {common.length > 0 && <EffectList title="Most common" items={common} />}
          {sections.length > 0 && (
            <details className="label-full" open={!summarised}>
              <summary>Full label text</summary>
              {sections.map(([key, title]) => (
                <div key={key}>
                  <h4>{title}</h4>
                  <p>{drug[key]}{drug[key]!.length >= LABEL_TEXT_CAP && "…"}</p>
                </div>
              ))}
            </details>
          )}
        </>
      )}

      <h3 className="plain-h">Why it's the most likely</h3>
      {scored.length > 0 ? <Reasons answers={scored} /> : <p className="drug-detail">Nothing scored for this drug.</p>}
    </>
  );
}

function EffectList({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="effects">
      <span>{title}</span>
      <ul>{items.map((e) => <li key={e}>{e}</li>)}</ul>
    </div>
  );
}

function Reasons({ answers, showAnswer = false }: { answers: Answer[]; showAnswer?: boolean }) {
  return (
    <ul className="plain-reasons">
      {answers.map((a) => (
        <li key={a.question}>
          <span className="plain-points">{points(a.points)}</span>
          <span>
            {showAnswer && <span className="plain-q">{a.short ?? a.question}: {ANSWER[a.answer]}</span>}
            {a.why}
          </span>
        </li>
      ))}
    </ul>
  );
}

// Page 2: every question for this drug, how the others scored, and the AI's take
function ReasonsPage({ card, top, rest }: { card: ReviewCard; top: RankedDrug; rest: RankedDrug[] }) {
  return (
    <>
      <h3 className="plain-h first">Each question</h3>
      <Reasons answers={top.candidate.answers} showAnswer />
      <p className="drug-detail">Total {top.score} ({category(top.score)}), for {top.reaction.toLowerCase()}.</p>

      {rest.length > 0 && (
        <>
          <h3 className="plain-h">Other drugs</h3>
          <ul className="plain-list">
            {rest.map((r) => (
              <li key={r.drug.name}>
                <span>{shortDrugName(r.drug.name)}</span>
                <span>{r.score}</span>
              </li>
            ))}
          </ul>
        </>
      )}

      <h3 className="plain-h">AI</h3>
      <AiSuggestion patientId={card.patient.id} highlight={top.drug.name} />
    </>
  );
}
