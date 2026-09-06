import { lazy, Suspense, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ArrowDownRight,
  ArrowRight,
  CalendarDays,
  Check,
  CheckCheck,
  ChevronRight,
  CircleHelp,
  Clock3,
  Database,
  Download,
  FlaskConical,
  GitBranch,
  LayoutDashboard,
  LoaderCircle,
  LockKeyhole,
  PanelLeftClose,
  Play,
  Plus,
  ShieldCheck,
  SlidersHorizontal,
  Upload,
  Waypoints,
} from "lucide-react";
import {
  api,
  duration,
  exportJson,
  keyStore,
  slotLabel,
  type Dataset,
  type DatasetSummary,
  type Job,
} from "./api";
import Timeline from "./Timeline";
const Network = lazy(() => import("./Network"));

type Page = "overview" | "schedule" | "lab" | "datasets" | "audit";
const navigation = [
  { id: "overview", label: "Command center", icon: LayoutDashboard },
  { id: "schedule", label: "Block planner", icon: CalendarDays },
  { id: "lab", label: "Disruption lab", icon: FlaskConical },
  { id: "datasets", label: "Data sources", icon: Database },
  { id: "audit", label: "Plan history", icon: GitBranch },
] as const;

export default function App() {
  const client = useQueryClient();
  const [page, setPage] = useState<Page>("overview");
  const [chosenDataset, setChosenDataset] = useState("");
  const [chosenPlan, setChosenPlan] = useState("");
  const [locks, setLocks] = useState<string[]>([]);
  const [notice, setNotice] = useState("");
  const [key, setKey] = useState(keyStore.get);
  const [showKey, setShowKey] = useState(false);
  const [seed, setSeed] = useState(42);
  const [taskCount, setTaskCount] = useState(24);
  const [scenario, setScenario] = useState("task_overrun");
  const [magnitude, setMagnitude] = useState(2);
  const [target, setTarget] = useState("");
  const [downtimeWeight, setDowntimeWeight] = useState(10);
  const [churnWeight, setChurnWeight] = useState(1000);
  const datasets = useQuery({
    queryKey: ["datasets"],
    queryFn: () => api<DatasetSummary[]>("/datasets"),
  });
  const datasetId = chosenDataset || datasets.data?.[0]?.id || "";
  const loaded = useQuery({
    queryKey: ["dataset", datasetId],
    queryFn: () => api<{ dataset: Dataset }>(`/datasets/${datasetId}`),
    enabled: !!datasetId,
  });
  const jobs = useQuery({
    queryKey: ["jobs", datasetId],
    queryFn: () => api<Job[]>(`/jobs?dataset_id=${datasetId}`),
    enabled: !!datasetId,
    refetchInterval: 1000,
  });
  const history = jobs.data || [];
  const plans = history.filter(
    (j) => j.status === "completed" && j.result?.plan,
  );
  const currentJob = plans.find((j) => j.id === chosenPlan) || plans[0];
  const plan = currentJob?.result?.plan;
  const dataset = currentJob?.result?.dataset || loaded.data?.dataset;
  const independent = currentJob?.result?.baseline;
  const monthly = history.find(
    (j) => j.kind === "monthly" && j.status === "completed",
  );
  const stress = history.find(
    (j) =>
      j.kind === "stress" &&
      j.status === "completed" &&
      j.parent_job_id === currentJob?.id,
  )?.result;
  const active = history.find((j) => ["queued", "running"].includes(j.status));
  const failed = history.find((j) => j.status === "failed");
  const generate = useMutation({
    mutationFn: () =>
      api<{ id: string }>("/datasets/generate", {
        seed,
        tasks: taskCount,
        days: 28,
        sections: 4,
        trains: 28,
      }),
    onSuccess: (data) => {
      setChosenDataset(data.id);
      setChosenPlan("");
      setLocks([]);
      setNotice("Synthetic dataset generated. Ready to plan.");
      client.invalidateQueries({ queryKey: ["datasets"] });
    },
  });
  const importData = useMutation({
    mutationFn: (data: unknown) => api<{ id: string }>("/datasets", data),
    onSuccess: (data) => {
      setChosenDataset(data.id);
      setChosenPlan("");
      setLocks([]);
      setNotice("Dataset validated and imported.");
      client.invalidateQueries({ queryKey: ["datasets"] });
    },
  });
  const submit = useMutation({
    mutationFn: (kind: string) =>
      api<Job>("/jobs", {
        dataset_id: datasetId,
        kind,
        options: {
          time_limit: 8,
          weights: { downtime: downtimeWeight, changed: churnWeight },
          commitments: monthly?.result?.commitments || {},
          locked_task_ids: kind === "recovery" ? locks : [],
        },
        ...(kind === "stress" || kind === "recovery"
          ? { parent_job_id: currentJob?.id }
          : {}),
        ...(kind === "recovery"
          ? {
              disruption: {
                kind: scenario,
                magnitude,
                target_id: target || null,
              },
            }
          : {}),
        count: 20,
      }),
    onSuccess: () => {
      setNotice("Run submitted. Track its status in Plan history.");
      setChosenPlan("");
      client.invalidateQueries({ queryKey: ["jobs", datasetId] });
    },
  });
  const busy = !!active || submit.isPending;
  const error =
    datasets.error ||
    loaded.error ||
    jobs.error ||
    generate.error ||
    importData.error ||
    submit.error;
  const baseComparable =
    plan?.verified &&
    independent?.verified &&
    currentJob?.kind === "optimize" &&
    plan.assignments.length === independent.assignments.length &&
    plan.assignments.every((a) =>
      independent.assignments.some((b) => b.task_id === a.task_id),
    );
  const saved = baseComparable
    ? independent.metrics.downtime_minutes - plan.metrics.downtime_minutes
    : undefined;
  const targets = dataset
    ? scenario === "train_delay"
      ? dataset.trains
      : scenario === "crew_loss"
        ? dataset.resources
        : ["corridor_reduction", "emergency"].includes(scenario)
          ? dataset.sections
          : dataset.tasks
    : [];
  function selectDataset(id: string) {
    setChosenDataset(id);
    setChosenPlan("");
    setLocks([]);
    setTarget("");
    setNotice("");
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setPage("overview");
          }}
        >
          <span className="brand-icon">
            <ShieldCheck size={25} />
          </span>
          <span>
            railshield<span className="brand-sub">OPERATIONS INTELLIGENCE</span>
          </span>
        </a>
        <div className="workspace-label">
          PLANNING WORKSPACE
          <PanelLeftClose size={14} />
        </div>
        <nav aria-label="Main navigation">
          {navigation.map((item) => (
            <button
              key={item.id}
              className={`nav-item ${page === item.id ? "selected" : ""}`}
              aria-label={item.label}
              aria-current={page === item.id ? "page" : undefined}
              onClick={() => setPage(item.id)}
            >
              <item.icon size={18} />
              <span>{item.label}</span>
              {item.id === "lab" && <span className="nav-tag">LAB</span>}
            </button>
          ))}
        </nav>
        <div className="sidebar-note">
          <div>
            <Waypoints size={18} />
            <strong>Coordinated by design</strong>
          </div>
          <p>
            One possession.
            <br />
            Three departments.
            <br />
            More railway availability.
          </p>
          <span>
            ENG <i /> TRD <i /> S&T
          </span>
        </div>
        <div className="sidebar-bottom">
          <button onClick={() => setShowKey(!showKey)}>
            <CircleHelp size={17} /> Connection settings
          </button>
          <div className="profile">
            <span>RS</span>
            <div>
              <strong>Planning team</strong>
              <small>SIH26027 · Decision support</small>
            </div>
          </div>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <div>
            Workspace
            <ChevronRight size={13} />
            <strong>{navigation.find((n) => n.id === page)?.label}</strong>
          </div>
          <div className="topbar-right">
            <button
              className="icon-button mobile-connection"
              aria-label="Connection settings"
              onClick={() => setShowKey(!showKey)}
            >
              <SlidersHorizontal size={14} />
            </button>
            <span className="status-dot" />
            {dataset?.synthetic
              ? "Synthetic environment"
              : "Planning environment"}
            <span className="vertical-rule" />
            <span>IST · UTC +05:30</span>
          </div>
        </header>
        <div className="page-content">
          <div className="page-title">
            <div>
              <div className="eyebrow">RAILWAY MAINTENANCE PLANNING</div>
              <h1>{navigation.find((n) => n.id === page)?.label}</h1>
              <p>
                {page === "lab"
                  ? "Test the plan against disruption. Recover with less change."
                  : page === "datasets"
                    ? "Traceable inputs. Repeatable experiments."
                    : page === "audit"
                      ? "Every planning run, preserved and inspectable."
                      : "Coordinate maintenance. Keep the network moving."}
              </p>
            </div>
            <div className="actions">
              {plan && (
                <button
                  className="secondary"
                  onClick={() =>
                    exportJson(
                      `railshield-plan-${currentJob.id}.json`,
                      currentJob,
                    )
                  }
                >
                  <Download size={16} />
                  Export plan
                </button>
              )}
              <button
                className="primary"
                disabled={!dataset || busy}
                onClick={() => submit.mutate("optimize")}
              >
                {busy ? (
                  <LoaderCircle size={16} className="spin" />
                ) : (
                  <Play size={15} fill="currentColor" />
                )}
                Generate plan
              </button>
            </div>
          </div>
          {showKey && (
            <form
              className="connection panel"
              onSubmit={(e) => {
                e.preventDefault();
                keyStore.set(key);
                client.invalidateQueries();
                setShowKey(false);
              }}
            >
              <label>
                API bearer key
                <input
                  type="password"
                  value={key}
                  onChange={(e) => setKey(e.target.value)}
                  placeholder="Required when API authentication is enabled"
                />
              </label>
              <button className="primary">Connect</button>
              <p>
                Kept in this browser session. Local development can run without
                a key.
              </p>
            </form>
          )}
          {error && (
            <div className="alert error" role="alert">
              {error.message}
              <button
                className="text-button"
                onClick={() => {
                  setShowKey(true);
                  client.invalidateQueries();
                }}
              >
                Check connection
              </button>
            </div>
          )}
          {notice && (
            <div className="notice" role="status">
              <Check size={15} />
              {notice}
              <button
                aria-label="Dismiss notification"
                onClick={() => setNotice("")}
              >
                ×
              </button>
            </div>
          )}
          {active && (
            <div className="alert progress" role="status">
              <LoaderCircle size={16} className="spin" />
              {active.kind} · {active.status}. Solver runs in a separate worker.
            </div>
          )}
          {!active && failed && (
            <div className="alert error">Latest failed job: {failed.error}</div>
          )}
          <div className="context-bar">
            <div>
              <span className="context-icon">
                <Waypoints size={18} />
              </span>
              <label>
                Planning dataset
                <select
                  aria-label="Planning dataset"
                  value={datasetId}
                  onChange={(e) => selectDataset(e.target.value)}
                >
                  {!datasets.data?.length && (
                    <option value="">No dataset loaded</option>
                  )}
                  {datasets.data?.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="context-meta">
              {dataset ? (
                <>
                  <CalendarDays size={16} />
                  <span>{Math.ceil(dataset.horizon / 96)}-day horizon</span>
                  <span className="badge neutral">
                    {dataset.sections.length} sections
                  </span>
                  <span className="badge neutral">
                    {dataset.synthetic ? "SYNTHETIC" : "IMPORTED"}
                  </span>
                </>
              ) : (
                <span>Import data or create a reproducible demo</span>
              )}
            </div>
          </div>
          {!dataset && !loaded.isLoading && page !== "datasets" && (
            <section className="empty-state panel">
              <ShieldCheck size={38} />
              <h2>Your planning workspace is ready</h2>
              <p>
                Generate a seeded northern corridor dataset to explore
                coordinated maintenance, train exclusions, and recovery.
              </p>
              <button
                className="primary"
                disabled={generate.isPending}
                onClick={() => generate.mutate()}
              >
                <Plus size={16} />
                {generate.isPending ? "Generating…" : "Create demo dataset"}
              </button>
              <button
                className="text-button"
                onClick={() => setPage("datasets")}
              >
                Or import a dataset <ArrowRight size={14} />
              </button>
            </section>
          )}
          {(datasets.isLoading || loaded.isLoading) && (
            <div className="loading" role="status">
              <LoaderCircle className="spin" />
              Loading workspace…
            </div>
          )}
          {dataset && (page === "overview" || page === "schedule") && (
            <>
              <div className="stats-grid">
                <Metric
                  label="MAINTENANCE DEMAND"
                  value={String(dataset.tasks.length).padStart(2, "0")}
                  caption={`${dataset.tasks.filter((t) => t.required).length} required · 3 departments`}
                  icon={<SlidersHorizontal size={18} />}
                />
                <Metric
                  label="PLANNED POSSESSION"
                  value={
                    plan?.verified
                      ? duration(plan.metrics.downtime_minutes)
                      : "—"
                  }
                  caption={
                    saved !== undefined
                      ? `${duration(Math.abs(saved))} ${saved >= 0 ? "saved" : "additional"} vs. independent`
                      : "Generate a verified plan to measure"
                  }
                  positive={saved !== undefined && saved > 0}
                  icon={<Clock3 size={18} />}
                />
                <Metric
                  label="SECTION AVAILABILITY"
                  value={
                    plan?.verified
                      ? `${plan.metrics.availability_percent.toFixed(2)}%`
                      : "—"
                  }
                  caption="Across the full planning horizon"
                  icon={<Activity size={18} />}
                />
                <Metric
                  label="SCHEDULED TASKS"
                  value={
                    plan?.verified
                      ? `${plan.assignments.length}/${dataset.tasks.length}`
                      : "—"
                  }
                  caption={
                    plan?.verified
                      ? `${plan.deferred.length} deferred · verified constraints`
                      : "Awaiting optimization"
                  }
                  icon={<CheckCheck size={18} />}
                />
              </div>
              <div className="planning-strip">
                <div>
                  <span className="step-number">01</span>
                  <div>
                    <strong>Monthly commitments</strong>
                    <small>
                      {monthly
                        ? `${Object.keys(monthly.result?.commitments || {}).length} tasks allocated · ${monthly.result?.status}`
                        : "Allocate work to weekly budgets"}
                    </small>
                  </div>
                </div>
                <button
                  className="text-button"
                  disabled={busy}
                  onClick={() => submit.mutate("monthly")}
                >
                  Build monthly plan <ArrowRight size={15} />
                </button>
                <span className="strip-divider" />
                <div>
                  <span className="step-number">02</span>
                  <div>
                    <strong>Detailed schedule</strong>
                    <small>
                      {plan
                        ? `${plan.status} · ${plan.solver_seconds.toFixed(2)}s solver time`
                        : "Resolve exact windows and resources"}
                    </small>
                  </div>
                </div>
                <span
                  className={`badge ${plan?.verified ? "success" : "neutral"}`}
                >
                  {plan?.verified ? "CONSTRAINTS VERIFIED" : "NOT YET SOLVED"}
                </span>
              </div>
              {plan && !plan.verified && (
                <div className="alert error" role="alert">
                  <strong>{plan.status}</strong> {plan.diagnostics.join(" ")}
                </div>
              )}
              {page === "overview" && (
                <div className="overview-grid">
                  <section className="panel network-panel">
                    <div className="panel-heading">
                      <div>
                        <h2>Corridor overview</h2>
                        <p>
                          {dataset.synthetic
                            ? "Illustrative northern railway topology"
                            : "Imported section topology"}
                        </p>
                      </div>
                      <span className="badge neutral">
                        {dataset.sections.length} SECTIONS
                      </span>
                    </div>
                    <Suspense
                      fallback={
                        <div className="network loading">Loading topology…</div>
                      }
                    >
                      <Network dataset={dataset} plan={plan} />
                    </Suspense>
                    <div className="panel-footer">
                      <span>
                        <i className="inline-dot" /> Sections with planned
                        maintenance
                      </span>
                      <button
                        className="text-button"
                        onClick={() => setPage("schedule")}
                      >
                        View schedule <ArrowRight size={14} />
                      </button>
                    </div>
                  </section>
                  <section className="panel comparison">
                    <div className="panel-heading">
                      <div>
                        <h2>The coordination advantage</h2>
                        <p>Same tasks. Shared possession.</p>
                      </div>
                      <ArrowDownRight size={20} />
                    </div>
                    <div className="comparison-bars">
                      <div>
                        <span>Independent</span>
                        <strong>
                          {independent?.verified
                            ? duration(independent.metrics.downtime_minutes)
                            : "—"}
                        </strong>
                      </div>
                      <div className="bar">
                        <i
                          style={{
                            width: independent?.verified ? "100%" : "0%",
                          }}
                        />
                      </div>
                      <div>
                        <span>RailShield</span>
                        <strong>
                          {plan?.verified
                            ? duration(plan.metrics.downtime_minutes)
                            : "—"}
                        </strong>
                      </div>
                      <div className="bar coordinated">
                        <i
                          style={{
                            width:
                              plan?.verified && independent?.verified
                                ? `${Math.min(100, (plan.metrics.downtime_minutes / Math.max(1, independent.metrics.downtime_minutes)) * 100)}%`
                                : "0%",
                          }}
                        />
                      </div>
                    </div>
                    <p className="comparison-note">
                      {saved !== undefined ? (
                        <>
                          <strong>
                            {(
                              (saved /
                                Math.max(
                                  1,
                                  independent!.metrics.downtime_minutes,
                                )) *
                              100
                            ).toFixed(1)}
                            %
                          </strong>{" "}
                          less possession time on the same task set
                        </>
                      ) : (
                        "A comparable baseline appears after optimization."
                      )}
                    </p>
                  </section>
                </div>
              )}
              <Timeline
                key={datasetId}
                dataset={dataset}
                plan={plan}
                locks={locks}
                onLock={(id) =>
                  setLocks((prev) =>
                    prev.includes(id)
                      ? prev.filter((x) => x !== id)
                      : [...prev, id],
                  )
                }
              />
              <div className="bottom-grid">
                <section className="panel">
                  <div className="panel-heading">
                    <div>
                      <h2>Maintenance register</h2>
                      <p>Required work and deferred demand remain visible.</p>
                    </div>
                    <span className="badge neutral">
                      {dataset.tasks.length} TASKS
                    </span>
                  </div>
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>Task / activity</th>
                          <th>Section</th>
                          <th>Duration</th>
                          <th>Priority</th>
                          <th>Placement · IST</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dataset.tasks.map((task) => {
                          const a = plan?.assignments.find(
                            (a) => a.task_id === task.id,
                          );
                          return (
                            <tr key={task.id}>
                              <td>
                                <span
                                  className={`dept-dot ${task.department.toLowerCase()}`}
                                />
                                <strong>{task.id}</strong>
                                <small>{task.title}</small>
                              </td>
                              <td>{task.section_id}</td>
                              <td>{duration(task.duration * 15)}</td>
                              <td>
                                <span
                                  className={`badge ${task.priority >= 8 ? "warning" : "neutral"}`}
                                >
                                  {task.priority}/10
                                </span>
                              </td>
                              <td>
                                {a
                                  ? slotLabel(dataset, a.start)
                                  : plan?.deferred.includes(task.id)
                                    ? "Deferred"
                                    : "Unscheduled"}
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </section>
                <section className="panel objective">
                  <div className="panel-heading">
                    <div>
                      <h2>Why this plan?</h2>
                      <p>Weighted objective contributions</p>
                    </div>
                  </div>
                  {plan?.verified ? (
                    <>
                      <div className="objective-total">
                        {plan.objective_value?.toLocaleString()}
                        <small>objective score</small>
                      </div>
                      {Object.entries(plan.objective).map(([name, value]) => (
                        <div className="objective-row" key={name}>
                          <span>{name.replace("_", " ")}</span>
                          <strong>{value.toLocaleString()}</strong>
                        </div>
                      ))}
                      <p>
                        Best bound: {plan.best_bound?.toLocaleString()}.{" "}
                        {plan.status === "OPTIMAL"
                          ? "Optimal for this discrete model."
                          : "Feasible incumbent; optimality is not proved."}
                      </p>
                    </>
                  ) : (
                    <p className="muted padded">
                      Generate a plan to inspect its cost breakdown.
                    </p>
                  )}
                  <div className="weight-controls">
                    <label>
                      Downtime weight <strong>{downtimeWeight}</strong>
                      <input
                        aria-label="Downtime weight"
                        type="range"
                        min="1"
                        max="100"
                        value={downtimeWeight}
                        onChange={(e) =>
                          setDowntimeWeight(Number(e.target.value))
                        }
                      />
                    </label>
                    <p>
                      Train exclusion and required deadlines are hard
                      constraints, never traded for a lower score.
                    </p>
                  </div>
                </section>
              </div>
            </>
          )}
          {dataset && page === "lab" && (
            <>
              <div className="lab-grid">
                <section className="panel">
                  <div className="panel-heading">
                    <div>
                      <h2>Inject a disruption</h2>
                      <p>Recover against the selected plan’s exact snapshot.</p>
                    </div>
                    <FlaskConical size={20} />
                  </div>
                  <div className="form-body">
                    <label>
                      Disruption type
                      <select
                        value={scenario}
                        onChange={(e) => {
                          setScenario(e.target.value);
                          setTarget("");
                        }}
                      >
                        <option value="task_overrun">
                          Maintenance overrun
                        </option>
                        <option value="train_delay">Train delay</option>
                        <option value="crew_loss">Crew capacity loss</option>
                        <option value="corridor_reduction">
                          Corridor window reduction
                        </option>
                        <option value="emergency">Emergency defect</option>
                      </select>
                    </label>
                    <label>
                      Target
                      <select
                        aria-label="Disruption target"
                        value={target}
                        onChange={(e) => setTarget(e.target.value)}
                      >
                        <option value="">First available target</option>
                        {targets.map((t) => (
                          <option key={t.id} value={t.id}>
                            {t.id}
                          </option>
                        ))}
                      </select>
                    </label>
                    <label>
                      {scenario === "crew_loss"
                        ? "Teams unavailable"
                        : "Magnitude in 15-minute slots"}
                      <input
                        type="number"
                        min="1"
                        max="12"
                        value={magnitude}
                        onChange={(e) => setMagnitude(Number(e.target.value))}
                      />
                    </label>
                    <label>
                      Stability weight <strong>{churnWeight}</strong>
                      <input
                        aria-label="Stability weight"
                        type="range"
                        min="0"
                        max="5000"
                        step="100"
                        value={churnWeight}
                        onChange={(e) => setChurnWeight(Number(e.target.value))}
                      />
                    </label>
                    <p className="lock-note">
                      <LockKeyhole size={15} />
                      {locks.length} locked tasks. Inspect timeline tasks to
                      change locks.
                    </p>
                    <button
                      className="primary"
                      disabled={
                        !plan?.verified ||
                        busy ||
                        magnitude < 1 ||
                        magnitude > 12
                      }
                      onClick={() => submit.mutate("recovery")}
                    >
                      <GitBranch size={16} />
                      Recover plan
                    </button>
                  </div>
                </section>
                <section className="panel">
                  <div className="panel-heading">
                    <div>
                      <h2>Recovery comparison</h2>
                      <p>Measured on the same disrupted instance</p>
                    </div>
                  </div>
                  {currentJob?.kind === "recovery" ? (
                    <div className="recovery-results">
                      <ComparisonMetric
                        title="Tasks changed"
                        a={
                          currentJob.result?.full_replan?.metrics.changed_tasks
                        }
                        b={plan?.metrics.changed_tasks}
                      />
                      <ComparisonMetric
                        title="Possession minutes"
                        a={
                          currentJob.result?.full_replan?.metrics
                            .downtime_minutes
                        }
                        b={plan?.metrics.downtime_minutes}
                      />
                      <p
                        className={`alert ${plan?.verified ? "progress" : "error"}`}
                      >
                        {plan?.verified
                          ? `Recovered and verified in ${plan.solver_seconds.toFixed(2)}s. $Recovery result saved.`
                          : `${plan?.status}: ${plan?.diagnostics.join(" ")}`}
                      </p>
                      <p>
                        Full replan does not preserve locks. Recovery preserves
                        every requested lock; conflicting locks cause
                        infeasibility.
                      </p>
                    </div>
                  ) : (
                    <div className="empty-small">
                      <GitBranch size={32} />
                      <h3>Ready for the unexpected</h3>
                      <p>
                        Run recovery to compare schedule changes with a full
                        replan.
                      </p>
                    </div>
                  )}
                </section>
              </div>
              <section className="panel">
                <div className="panel-heading">
                  <div>
                    <h2>Scenario stress test</h2>
                    <p>
                      20 seeded disruptions, evaluated against fixed task starts
                    </p>
                  </div>
                  <button
                    className="secondary"
                    disabled={!plan?.verified || busy}
                    onClick={() => submit.mutate("stress")}
                  >
                    <Play size={14} />
                    Run stress test
                  </button>
                </div>
                {stress?.results ? (
                  <div className="stress-results">
                    <div className="stress-score">
                      <strong>
                        {((stress.feasibility_rate || 0) * 100).toFixed(0)}%
                      </strong>
                      <span>
                        {stress.feasible} / {stress.evaluated} scenarios remain
                        feasible · {stress.invalid} invalid samples
                      </span>
                    </div>
                    <p>{stress.interpretation}</p>
                    <div className="scenario-list">
                      {stress.results.map((r, i) => (
                        <details key={i}>
                          <summary>
                            <span>
                              {r.scenario.kind.replaceAll("_", " ")} ·{" "}
                              {r.scenario.target_id}
                            </span>
                            <span
                              className={`badge ${r.feasible ? "success" : "warning"}`}
                            >
                              {r.feasible
                                ? "Feasible"
                                : r.valid
                                  ? "Violated"
                                  : "Invalid input"}
                            </span>
                          </summary>
                          <p>
                            {r.violations.join(" · ") ||
                              "All modeled hard constraints hold."}
                          </p>
                        </details>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="empty-small">
                    <p>
                      No experiment yet. Results measure synthetic scenarios,
                      not operational reliability.
                    </p>
                  </div>
                )}
              </section>
            </>
          )}
          {page === "datasets" && (
            <div className="lab-grid">
              <section className="panel">
                <div className="panel-heading">
                  <div>
                    <h2>Generate synthetic data</h2>
                    <p>Reproducible fixtures for demonstrations and tests</p>
                  </div>
                  <Database size={20} />
                </div>
                <form
                  className="form-body"
                  onSubmit={(e) => {
                    e.preventDefault();
                    generate.mutate();
                  }}
                >
                  <label>
                    Random seed
                    <input
                      type="number"
                      min="0"
                      max="2147483647"
                      value={seed}
                      onChange={(e) => setSeed(Number(e.target.value))}
                    />
                  </label>
                  <label>
                    Maintenance tasks
                    <input
                      type="number"
                      min="1"
                      max="200"
                      value={taskCount}
                      onChange={(e) => setTaskCount(Number(e.target.value))}
                    />
                  </label>
                  <p>
                    4 sections · 28 days · 28 train occupations. Three
                    department source exports are available through the CLI.
                  </p>
                  <button className="primary" disabled={generate.isPending}>
                    <Plus size={16} />
                    Generate dataset
                  </button>
                </form>
              </section>
              <section className="panel">
                <div className="panel-heading">
                  <div>
                    <h2>Import / export</h2>
                    <p>Version 1 validated JSON contract</p>
                  </div>
                  <Upload size={20} />
                </div>
                <div className="form-body">
                  <label className="upload-zone">
                    <Upload size={26} />
                    <strong>Choose a dataset JSON file</strong>
                    <span>
                      2 MB maximum · IDs, windows and dependencies validated
                    </span>
                    <input
                      type="file"
                      accept=".json,application/json"
                      onChange={async (e) => {
                        const file = e.target.files?.[0];
                        if (!file) return;
                        if (file.size > 2_000_000) {
                          setNotice("File exceeds the 2 MB limit.");
                          return;
                        }
                        try {
                          importData.mutate(JSON.parse(await file.text()));
                        } catch {
                          setNotice(
                            "Invalid JSON file. Please check its syntax.",
                          );
                        }
                        e.target.value = "";
                      }}
                    />
                  </label>
                  <button
                    className="secondary"
                    disabled={!dataset}
                    onClick={() =>
                      exportJson("railshield-dataset.json", dataset)
                    }
                  >
                    <Download size={16} />
                    Export current dataset
                  </button>
                  <p>
                    TMS, SMMS, TDMS and COA exports are synthetic mappings. Live
                    railway connectors require validated source specifications.
                  </p>
                </div>
              </section>
            </div>
          )}
          {dataset && page === "audit" && (
            <section className="panel">
              <div className="panel-heading">
                <div>
                  <h2>Planning runs</h2>
                  <p>Immutable results and input lineage</p>
                </div>
                <span className="badge neutral">
                  {history.length} RECENT RUNS
                </span>
              </div>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Run</th>
                      <th>Created</th>
                      <th>Status</th>
                      <th>Result</th>
                      <th>Inspect</th>
                    </tr>
                  </thead>
                  <tbody>
                    {history.map((job) => (
                      <tr key={job.id}>
                        <td>
                          <strong>{job.kind}</strong>
                          <small>{job.id.slice(0, 8)}</small>
                        </td>
                        <td>
                          {new Date(
                            job.created_at.endsWith("Z") ||
                              job.created_at.includes("+")
                              ? job.created_at
                              : `${job.created_at}Z`,
                          ).toLocaleString()}
                        </td>
                        <td>
                          <span
                            className={`badge ${job.status === "completed" ? "success" : "neutral"}`}
                          >
                            {job.status}
                          </span>
                        </td>
                        <td>
                          {job.result?.plan?.status ||
                            job.result?.status ||
                            job.error ||
                            "—"}
                        </td>
                        <td>
                          {job.result?.plan && (
                            <button
                              className="text-button"
                              onClick={() => {
                                setChosenPlan(job.id);
                                setLocks([]);
                                setPage(
                                  job.kind === "recovery" ? "lab" : "schedule",
                                );
                              }}
                            >
                              Open plan <ArrowRight size={14} />
                            </button>
                          )}
                          <button
                            className="text-button"
                            onClick={() =>
                              exportJson(`railshield-${job.id}.json`, job)
                            }
                          >
                            JSON <Download size={13} />
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                {!history.length && (
                  <div className="empty-small">No planning runs yet.</div>
                )}
              </div>
            </section>
          )}
          <footer className="page-footer">
            <span>
              <ShieldCheck size={14} /> RailShield · Verified constraints,
              transparent trade-offs
            </span>
            <span>Decision support · SIH26027</span>
          </footer>
        </div>
      </main>
    </div>
  );
}
function Metric({
  label,
  value,
  caption,
  icon,
  positive,
}: {
  label: string;
  value: string;
  caption: string;
  icon: React.ReactNode;
  positive?: boolean;
}) {
  return (
    <section className="metric">
      <div>
        <span>{label}</span>
        {icon}
      </div>
      <strong>{value}</strong>
      <p className={positive ? "positive" : ""}>
        {positive && <ArrowDownRight size={14} />}
        {caption}
      </p>
    </section>
  );
}
function ComparisonMetric({
  title,
  a,
  b,
}: {
  title: string;
  a?: number;
  b?: number;
}) {
  return (
    <div className="compare-metric">
      <h3>{title}</h3>
      <div>
        <span>
          Full replan<strong>{a ?? "—"}</strong>
        </span>
        <ArrowRight size={18} />
        <span>
          Stable recovery<strong>{b ?? "—"}</strong>
        </span>
      </div>
    </div>
  );
}
