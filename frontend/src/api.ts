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

const HOSTED_STATE_KEY = "railshield-hosted-state-v1";
const HOSTED = import.meta.env.VITE_SERVERLESS === "true";
export const hostedMode = HOSTED;

type StoredDataset = DatasetSummary & { dataset: Dataset };
type HostedState = { datasets: StoredDataset[]; jobs: Job[] };
type HostedJobRequest = {
  dataset_id: string;
  kind: string;
  options: Record<string, unknown>;
  parent_job_id?: string;
  disruption?: unknown;
  count?: number;
};

function readHostedState(): HostedState {
  try {
    const value = JSON.parse(localStorage.getItem(HOSTED_STATE_KEY) || "null");
    if (Array.isArray(value?.datasets) && Array.isArray(value?.jobs)) return value;
  } catch {
    localStorage.removeItem(HOSTED_STATE_KEY);
  }
  return { datasets: [], jobs: [] };
}

function writeHostedState(state: HostedState) {
  try {
    localStorage.setItem(
      HOSTED_STATE_KEY,
      JSON.stringify({ datasets: state.datasets.slice(0, 10), jobs: state.jobs.slice(0, 30) }),
    );
  } catch {
    throw new Error("Browser storage is full. Export results and clear old site data.");
  }
}

async function statelessRequest<T>(path: string, body: unknown): Promise<T> {
  const response = await fetch(`/api/v1/stateless${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const detail = data.detail;
    throw new Error(
      typeof detail === "string"
        ? detail
        : Array.isArray(detail)
          ? detail.map((item) => item.msg).join("; ")
          : `Hosted planning request failed (${response.status}).`,
    );
  }
  return response.json();
}

async function hostedApi<T>(path: string, body?: unknown): Promise<T> {
  const state = readHostedState();
  if (path === "/datasets" && body === undefined) {
    return state.datasets.map((item) => ({
      id: item.id,
      name: item.name,
      synthetic: item.synthetic,
      tasks: item.tasks,
      created_at: item.created_at,
    })) as T;
  }
  if (path === "/datasets/generate") {
    const result = await statelessRequest<{ dataset: Dataset }>("/generate", body);
    const stored: StoredDataset = {
      id: crypto.randomUUID(),
      name: result.dataset.name,
      synthetic: result.dataset.synthetic,
      tasks: result.dataset.tasks.length,
      created_at: new Date().toISOString(),
      dataset: result.dataset,
    };
    state.datasets.unshift(stored);
    writeHostedState(state);
    return { id: stored.id, dataset: stored.dataset } as T;
  }
  if (path === "/datasets" && body !== undefined) {
    const result = await statelessRequest<{ dataset: Dataset }>("/validate", body);
    const stored: StoredDataset = {
      id: crypto.randomUUID(),
      name: result.dataset.name,
      synthetic: result.dataset.synthetic,
      tasks: result.dataset.tasks.length,
      created_at: new Date().toISOString(),
      dataset: result.dataset,
    };
    state.datasets.unshift(stored);
    writeHostedState(state);
    return { id: stored.id, dataset: stored.dataset } as T;
  }
  const datasetMatch = path.match(/^\/datasets\/([^/?]+)$/);
  if (datasetMatch) {
    const stored = state.datasets.find((item) => item.id === datasetMatch[1]);
    if (!stored) throw new Error("Dataset not found in this browser.");
    return { id: stored.id, dataset: stored.dataset } as T;
  }
  if (path.startsWith("/jobs?") && body === undefined) {
    const datasetId = new URLSearchParams(path.split("?")[1]).get("dataset_id");
    return state.jobs.filter((job) => !datasetId || job.dataset_id === datasetId) as T;
  }
  if (path === "/jobs" && body !== undefined) {
    const request = body as HostedJobRequest;
    const stored = state.datasets.find((item) => item.id === request.dataset_id);
    if (!stored) throw new Error("Dataset not found in this browser.");
    const parent = request.parent_job_id
      ? state.jobs.find((job) => job.id === request.parent_job_id)
      : undefined;
    const effectiveDataset = parent?.result?.dataset || stored.dataset;
    const result = await statelessRequest<Job["result"]>("/execute", {
      dataset: effectiveDataset,
      kind: request.kind,
      options: request.options,
      parent_plan: parent?.result?.plan,
      parent_job_id: request.parent_job_id,
      disruption: request.disruption,
      count: request.count,
    });
    const job: Job = {
      id: crypto.randomUUID(),
      parent_job_id: request.parent_job_id || null,
      dataset_id: request.dataset_id,
      kind: request.kind,
      status: "completed",
      error: null,
      created_at: new Date().toISOString(),
      result,
    };
    state.jobs.unshift(job);
    writeHostedState(state);
    return job as T;
  }
  throw new Error(`Hosted mode does not support ${path}.`);
}

export async function api<T>(path: string, body?: unknown): Promise<T> {
  if (HOSTED) return hostedApi<T>(path, body);
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
