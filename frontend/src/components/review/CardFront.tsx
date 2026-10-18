import { day } from "../../data/dates";
import { caseName } from "../../data/people";
import { isComplication, plainName, plainSmoking } from "../../data/plainNames";
import type { ReviewCard } from "./reviewCards";
import { DECISION_LABEL, type Decision } from "./useDecisions";

const MAX_CONDITIONS = 3;

// "Nausea" -> "nausea" mid-sentence, but leave acronyms ("ADHD", "UTIs") alone
const lowerFirst = (s: string) => (/^[A-Z][a-z]/.test(s) ? s[0].toLowerCase() + s.slice(1) : s);

// ["Nausea", "Fatigue", "Pain 2/10"] -> "Nausea, fatigue and pain 2/10"
function list(items: string[]) {
  const words = items.map((s, i) => (i === 0 ? s : lowerFirst(s)));
  return words.length <= 1 ? words.join("") : `${words.slice(0, -1).join(", ")} and ${words[words.length - 1]}`;
}

// Front: who the patient is and what happened to them. Medications are on the back.
export default function CardFront({ card, previous }: { card: ReviewCard; previous?: Decision }) {
  const { patient } = card;
  const d = patient.details;
  const problems = patient.assessment.filter((a) => a.assessable).map((a) => a.reaction);
  const symptoms = (patient.felt ?? []).map((f) => plainName(f.text));
  const conditions = [...new Set([...(d?.existing_conditions ?? [])].reverse()
    .filter((c) => !isComplication(c)).map(plainName))]; // most recent first
  const shown = conditions.slice(0, MAX_CONDITIONS);
  const more = conditions.length - shown.length;

  const facts = [
    ["BMI", d?.bmi],
    ["Blood pressure", d?.blood_pressure],
    ["Smoking", d?.smoking && plainSmoking(d.smoking)],
  ].filter((f): f is [string, string] => !!f[1]);

  return (
    <div className="front">
      <div className="front-top">
        <h2 className="front-name">{caseName(patient)}</h2>
        <p className="front-meta">
          {[patient.age && `${patient.age}`, patient.sex, d?.place].filter(Boolean).join(", ")}
        </p>
      </div>

      <div className="front-symptoms">
        {problems.map((s) => <span key={s}>{s}</span>)}
        {patient.onset && <p className="front-onset">Started {day(patient.onset)}</p>}
      </div>

      <div className="front-info">
        {symptoms.length > 0 && (
          <section>
            <h3>Symptoms</h3>
            <p>{list(symptoms)}</p>
          </section>
        )}

        {(facts.length > 0 || shown.length > 0) && (
          <section>
            <h3>Health</h3>
            {facts.length > 0 && (
              <dl className="front-facts">
                {facts.map(([k, v]) => (
                  <div key={k}><dt>{k}</dt><dd>{v}</dd></div>
                ))}
              </dl>
            )}
            {shown.length > 0 && <p>{list(more > 0 ? [...shown, `${more} more`] : shown)}</p>}
          </section>
        )}

        {previous && <span className="front-previous">{DECISION_LABEL[previous]}</span>}
      </div>
    </div>
  );
}
