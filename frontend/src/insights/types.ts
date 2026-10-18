// Shape of frontend/public/insights.json, written by `python -m analytics` (analytics/model.py)

export interface PairStat {
  drug: string; // drug name as shown in the app (only on case pairs)
  ingredient?: string;
  condition: string;
  n: number; // people on the drug who then got the condition
  exposed: number; // people on the drug
  rate_exposed: number;
  rate_unexposed: number;
  prr: number | null; // how many times more often (null when n = 0)
  prr_low: number | null; // 95% lower bound
  chi2: number | null;
  dated: number; // of n, how many had dates confirming the condition came after the drug
  treats: number; // people the drug was prescribed FOR this condition
  signal: boolean; // Evans criteria: n >= 3, PRR >= 2, chi-square >= 4
}

export interface Cluster {
  id: number;
  size: number;
  label: string;
  features: { feature: string; kind: "drug" | "cond"; share: number; overall: number }[];
}

export interface Point {
  id: string;
  trial: string | null;
  cluster: number;
  x: number;
  y: number;
  outlier: number; // 0 = typical for its group, 1 = most unusual
  signals: number;
}

export interface CaseInsight {
  id: string; // matches Patient.id in data.json
  person_id: string;
  cluster: number;
  cluster_label: string;
  placed: "person" | "projected"; // projected = placed by its drugs/conditions (person not in the population)
  x: number;
  y: number;
  unusual: number; // distance from its group's centre, in typical distances
  priority: number; // 0-100: swipe higher first
  pairs: PairStat[];
  similar: { id: string; similarity: number }[];
}

export interface GraphNode {
  id: string;
  label: string;
  kind: "drug" | "condition";
  count: number;
}

export interface GraphLink {
  source: string;
  target: string;
  kind: "signal" | "treats" | "co_prescribed";
  n: number;
  prr?: number;
  // signal lines only: the numbers behind "x times as often"
  exposed?: number;
  rate_exposed?: number;
  rate_unexposed?: number;
  dated?: number;
}

export interface Insights {
  generated_at: string;
  source: string;
  params: { min_support: number; min_signal_n: number; window_days: number; clusters: number; seed: number };
  counts: { patients: number; cases: number; features: number; signals: number };
  caveats: string[];
  axes: { explained: number; top: { feature: string; kind: string; weight: number }[] }[];
  clusters: Cluster[];
  trials: { name: string; patients: number }[];
  points: Point[];
  cases: CaseInsight[];
  signals: PairStat[];
  indications: { drug: string; condition: string; n: number }[];
  graph: { nodes: GraphNode[]; links: GraphLink[] };
}
