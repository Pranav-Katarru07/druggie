import { useEffect, useState, type ReactNode } from "react";
import type { Patient } from "../types";
import { PatientsContext, type PatientsState } from "./patientsContext";

// Loads data.json (written by extractData.py) once and shares it with every page
export default function PatientsProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<PatientsState>({ status: "loading" });

  useEffect(() => {
    fetch("/data.json")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then((patients: Patient[]) => setState({ status: "ready", patients }))
      .catch(() => setState({ status: "error", message: "Couldn't load data.json. Run `python3 extractData.py` first." }));
  }, []);

  return <PatientsContext.Provider value={state}>{children}</PatientsContext.Provider>;
}
