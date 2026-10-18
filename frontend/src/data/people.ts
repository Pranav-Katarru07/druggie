import type { Patient } from "../types";

export interface Person {
  id: string;
  name: string;
  sex: string;
  age: string | null; // at their most recent case
  cases: Patient[];
}

export function caseName(c: Patient) {
  return c.name || `Patient ${c.id}`;
}

// Synthea cases for the same person share person_id; FAERS reports are one person each
export function groupPeople(cases: Patient[]): Person[] {
  const people = new Map<string, Person>();
  for (const c of cases) {
    const id = c.person_id ?? c.id;
    const person = people.get(id) ?? { id, name: caseName(c), sex: c.sex, age: c.age, cases: [] };
    person.cases.push(c);
    person.age = c.age ?? person.age;
    people.set(id, person);
  }
  return [...people.values()].sort((a, b) => a.name.localeCompare(b.name));
}
