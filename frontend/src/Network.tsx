import { useEffect, useRef } from "react";
import cytoscape from "cytoscape";
import type { Dataset, Plan } from "./api";
export default function Network({
  dataset,
  plan,
}: {
  dataset: Dataset;
  plan?: Plan;
}) {
  const container = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!container.current) return;
    const stations = [
      ...new Set(
        dataset.sections.flatMap((s) => [s.from_station, s.to_station]),
      ),
    ];
    const tokens = getComputedStyle(document.documentElement);
    const teal = tokens.getPropertyValue("--teal").trim();
    const ink = tokens.getPropertyValue("--ink").trim();
    const line = tokens.getPropertyValue("--line").trim();
    const graph = cytoscape({
      container: container.current,
      userZoomingEnabled: false,
      userPanningEnabled: false,
      boxSelectionEnabled: false,
      elements: [
        ...stations.map((name, i) => ({
          data: { id: `station:${name}`, label: name },
          position: { x: 50 + i * 125, y: 70 + (i % 2) * 25 },
        })),
        ...dataset.sections.map((s) => ({
          data: {
            id: `section:${s.id}`,
            source: `station:${s.from_station}`,
            target: `station:${s.to_station}`,
            planned: plan?.blocks.some((b) => b.section_id === s.id) ? 1 : 0,
          },
        })),
      ],
      layout: { name: "preset", fit: true, padding: 35 },
      style: [
        {
          selector: "node",
          style: {
            "background-color": "#ffffff",
            "border-color": teal,
            "border-width": 3,
            width: 13,
            height: 13,
            label: "data(label)",
            "font-size": 12,
            color: ink,
            "text-margin-y": 13,
            "text-valign": "bottom",
          },
        },
        {
          selector: "edge",
          style: { width: 3, "line-color": line, "curve-style": "bezier" },
        },
        { selector: "edge[planned = 1]", style: { "line-color": teal } },
      ],
    });
    const observer = new ResizeObserver(() => {
      graph.resize();
      graph.fit(undefined, 35);
    });
    observer.observe(container.current);
    return () => {
      observer.disconnect();
      graph.destroy();
    };
  }, [dataset, plan]);
  return (
    <div>
      <div ref={container} className="network" aria-hidden="true" />
      <p className="sr-only">
        Network:{" "}
        {dataset.sections
          .map((s) => `${s.from_station} to ${s.to_station}`)
          .join(", ")}
        . Planned sections are listed in the schedule.
      </p>
    </div>
  );
}
