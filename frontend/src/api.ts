export type Department = "ENG" | "SNT" | "TRD";
export type Window = { start: number; end: number };
export type Task = {
  id: string;
  title: string;
  department: Department;
  section_id: string;
  activity: string;
  duration: number;
  earliest: number;
  deadline: number;
  priority: number;
  required: boolean;
  demands: Record<string, number>;
  predecessors: string[];
};
export type Dataset = {
  name: string;
  synthetic: boolean;
  seed: number;
  epoch: string;
  slot_minutes: number;
  horizon: number;
  sections: {
    id: string;
    name: string;
    from_station: string;
    to_station: string;
    windows: Window[];
  }[];
  resources: { id: string; name: string; capacity: number }[];
  tasks: Task[];
  trains: ({ id: string; section_id: string } & Window)[];
};
export type DatasetSummary = {
  id: string;
  name: string;
  synthetic: boolean;
  tasks: number;
  created_at: string;
};
export type Assignment = Window & { task_id: string };
export type Plan = {
  status: string;
  assignments: Assignment[];
  deferred: string[];
  blocks: (Window & { section_id: string; task_ids: string[] })[];
  metrics: Record<string, number>;
  objective: Record<string, number>;
  verified: boolean;
  diagnostics: string[];
  solver_seconds: number;
  best_bound: number | null;
  objective_value: number | null;
};
export type Stress = {
  evaluated: number;
  feasible: number;
  feasibility_rate: number | null;
  invalid: number;
  interpretation: string;
  results: {
    scenario: { kind: string; magnitude: number; target_id: string };
    feasible: boolean;
    valid: boolean;
    violations: string[];
  }[];
};
export type Job = {
  id: string;
  parent_job_id: string | null;
  dataset_id: string;
  kind: string;
  status: string;
  error: string | null;
  created_at: string;
  result:
    | ({
        plan?: Plan;
        baseline?: Plan;
        full_replan?: Plan;
        dataset?: Dataset;
        commitments?: Record<string, number>;
        status?: string;
        advisory?: boolean;
      } & Partial<Stress>)
    | null;
};
export const keyStore = {
  get: () => sessionStorage.getItem("railshield-key") || "",
  set: (key: string) => sessionStorage.setItem("railshield-key", key),
};
export async function api<T>(path: string, body?: unknown): Promise<T> {
  const key = keyStore.get();
  const response = await fetch(`/api/v1${path}`, {
    method: body === undefined ? "GET" : "POST",
    headers: {
      "Content-Type": "application/json",
      ...(key ? { Authorization: `Bearer ${key}` } : {}),
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(
      typeof data.detail === "string"
        ? data.detail
        : `Request failed (${response.status}). Check the input format and connection.`,
    );
  }
  return response.json();
}
export function exportJson(name: string, data: unknown) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(data, null, 2)], { type: "application/json" }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  URL.revokeObjectURL(url);
}
export function duration(minutes: number) {
  return `${Math.floor(minutes / 60)}h ${Math.round(minutes % 60)
    .toString()
    .padStart(2, "0")}m`;
}
export function slotLabel(dataset: Dataset, slot: number) {
  // Show operational India time explicitly; never depend on the viewer's browser zone.
  return new Intl.DateTimeFormat("en-IN", {
    timeZone: "Asia/Kolkata",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(
    new Date(
      new Date(dataset.epoch).getTime() + slot * dataset.slot_minutes * 60000,
    ),
  );
}
