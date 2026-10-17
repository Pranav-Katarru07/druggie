import { createContext, useContext } from "react";
import type { Patient } from "../types";

export type PatientsState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; patients: Patient[] };

export const PatientsContext = createContext<PatientsState>({ status: "loading" });

const NO_PATIENTS: Patient[] = [];

export function usePatients() {
  return useContext(PatientsContext);
}

// The loaded patients, or a stable empty list while loading
export function usePatientList(): Patient[] {
  const state = usePatients();
  return state.status === "ready" ? state.patients : NO_PATIENTS;
}
