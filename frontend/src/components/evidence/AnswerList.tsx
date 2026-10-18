import type { Answer } from "../../types";

const ANSWER_LABEL = { yes: "Yes", no: "No", unknown: "Don't know" };

// The answered questions for one drug, in question order. Questions that scored 0 are hidden unless showZero is set.
export default function AnswerList({ answers, showZero = false }: { answers: Answer[]; showZero?: boolean }) {
  const shown = showZero ? answers : answers.filter((a) => a.points !== 0);
  if (shown.length === 0) return null;
  return (
    <ul className="why">
      {shown.map((a) => (
        <li key={a.question} className={a.points > 0 ? "pos" : a.points < 0 ? "neg" : "zero"}>
          <b>{a.points > 0 ? `+${a.points}` : a.points}</b>
          <span>
            <span className="why-q" title={a.question}>
              {a.number && `Q${a.number} · `}{a.short ?? a.question}
              <em className={`why-a ${a.answer}`}>{ANSWER_LABEL[a.answer]}</em>
            </span>
            {a.why}
          </span>
        </li>
      ))}
    </ul>
  );
}
