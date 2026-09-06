import { useState } from "react";
import { ChevronLeft, ChevronRight, LockKeyhole } from "lucide-react";
import { duration, slotLabel, type Dataset, type Plan, type Task } from "./api";
export default function Timeline({
  dataset,
  plan,
  locks,
  onLock,
}: {
  dataset: Dataset;
  plan?: Plan;
  locks: string[];
  onLock: (id: string) => void;
}) {
  const [day, setDay] = useState(0);
  const [selected, setSelected] = useState<Task | null>(null);
  const actualDay = Math.min(day, Math.ceil(dataset.horizon / 96) - 1);
  const start = actualDay * 96;
  const tasks = new Map(dataset.tasks.map((t) => [t.id, t]));
  const assignments =
    plan?.assignments.filter((a) => a.start < start + 96 && a.end > start) ||
    [];
  return (
    <section className="panel timeline-panel">
      <div className="panel-heading">
        <div>
          <h2>Possession timeline</h2>
          <p>Shared section time. Exact task placement.</p>
        </div>
        <div className="day-picker">
          <button
            className="icon-button"
            aria-label="Previous day"
            disabled={actualDay === 0}
            onClick={() => setDay(actualDay - 1)}
          >
            <ChevronLeft size={16} />
          </button>
          <span>{slotLabel(dataset, start).split(",")[0]} · IST</span>
          <button
            className="icon-button"
            aria-label="Next day"
            disabled={start + 96 >= dataset.horizon}
            onClick={() => setDay(actualDay + 1)}
          >
            <ChevronRight size={16} />
          </button>
        </div>
      </div>
      <div className="legend">
        <span>
          <i className="eng" />
          Engineering
        </span>
        <span>
          <i className="snt" />
          Signal & telecom
        </span>
        <span>
          <i className="trd" />
          Traction
        </span>
        <span>
          <i className="traffic" />
          Train occupation
        </span>
      </div>
      <div className="timeline-scroll">
        <div className="timeline-grid">
          <div className="timeline-axis">
            <span>SECTION / DEPARTMENT</span>
            <div>
              {Array.from({ length: 9 }, (_, i) => (
                <span key={i}>{String(i * 3).padStart(2, "0")}:00</span>
              ))}
            </div>
          </div>
          {dataset.sections.map((section) => (
            <div className="section-group" key={section.id}>
              <div className="section-label">
                <strong>{section.id}</strong>
                <span>
                  {section.from_station} → {section.to_station}
                </span>
              </div>
              <div className="track-lanes">
                {(["ENG", "SNT", "TRD"] as const).map((dept) => (
                  <div className="track-lane" key={dept}>
                    <span className="lane-label">{dept}</span>
                    {dataset.trains
                      .filter(
                        (t) =>
                          t.section_id === section.id &&
                          t.start < start + 96 &&
                          t.end > start,
                      )
                      .map((t) => (
                        <div
                          className="train-mark"
                          key={t.id}
                          title={`${t.id}: ${slotLabel(dataset, t.start)}`}
                          style={{
                            left: `${((Math.max(t.start, start) - start) / 96) * 100}%`,
                            width: `${((Math.min(t.end, start + 96) - Math.max(t.start, start)) / 96) * 100}%`,
                          }}
                        />
                      ))}
                    {assignments
                      .filter((a) => {
                        const t = tasks.get(a.task_id);
                        return (
                          t?.section_id === section.id && t.department === dept
                        );
                      })
                      .map((a) => (
                        <button
                          key={a.task_id}
                          className={`task-bar ${dept.toLowerCase()} ${locks.includes(a.task_id) ? "locked" : ""}`}
                          style={{
                            left: `${((Math.max(a.start, start) - start) / 96) * 100}%`,
                            width: `${((Math.min(a.end, start + 96) - Math.max(a.start, start)) / 96) * 100}%`,
                          }}
                          title={`${a.task_id}: ${slotLabel(dataset, a.start)} — ${slotLabel(dataset, a.end)}`}
                          aria-label={`Inspect ${a.task_id}`}
                          onClick={() => setSelected(tasks.get(a.task_id)!)}
                        >
                          {locks.includes(a.task_id) && (
                            <LockKeyhole size={10} />
                          )}
                          <span>{a.task_id}</span>
                        </button>
                      ))}
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="panel-footer">
        <span>
          {assignments.length} tasks on this day · 15-minute planning resolution
        </span>
        <span>Click a task to inspect or lock</span>
      </div>
      {selected && (
        <div className="task-detail" role="region" aria-label="Task details">
          <div>
            <span className={`badge ${selected.department.toLowerCase()}`}>
              {selected.id}
            </span>
            <h3>{selected.title}</h3>
            <p>
              {duration(selected.duration * 15)} · Priority {selected.priority}
              /10 · {selected.required ? "Required" : "Deferrable"}
            </p>
            <p>
              Uses{" "}
              {Object.entries(selected.demands)
                .map(([r, n]) => `${n} × ${r}`)
                .join(", ") || "no crew resource"}
              .
            </p>
            <p>
              Sharing requires declared activity compatibility, available crews,
              and no train conflict. The verifier checks each assignment.
            </p>
          </div>
          <div className="actions">
            <button className="secondary" onClick={() => onLock(selected.id)}>
              <LockKeyhole size={15} />
              {locks.includes(selected.id)
                ? "Unlock task"
                : "Lock for recovery"}
            </button>
            <button className="text-button" onClick={() => setSelected(null)}>
              Close
            </button>
          </div>
        </div>
      )}
    </section>
  );
}
