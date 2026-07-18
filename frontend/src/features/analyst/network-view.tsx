"use client";

import { useQuery } from "@tanstack/react-query";
import cytoscape from "cytoscape";
import { useEffect, useRef, useState } from "react";
import { ApiErrorState } from "@/components/api-error";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getNetwork } from "@/features/analyst/api";
import { useAnalystToken } from "@/features/analyst/access";

export function NetworkView() {
  const token = useAnalystToken();
  const container = useRef<HTMLDivElement | null>(null);
  const [selected, setSelected] = useState("Select an edge to inspect its governed relationship explanation.");
  const query = useQuery({ queryKey: ["analyst-network"], queryFn: () => getNetwork(token) });
  useEffect(() => {
    if (!container.current || !query.data) return;
    const graph = cytoscape({
      container: container.current,
      elements: [
        ...query.data.nodes.map((node) => ({ data: node })),
        ...query.data.edges.map((edge) => ({ data: edge })),
      ],
      style: [
        { selector: "node", style: { "background-color": "#0b6b4f", label: "data(label)", color: "#14211c", "font-size": 10, "text-valign": "bottom", "text-margin-y": 8, width: "mapData(occurrence_count, 1, 20, 24, 56)", height: "mapData(occurrence_count, 1, 20, 24, 56)" } },
        { selector: 'node[entity_type = "INCIDENT"]', style: { "background-color": "#b54708", shape: "round-rectangle" } },
        { selector: "edge", style: { width: "mapData(weight, 1, 10, 1, 6)", "line-color": "#9aaba2", "target-arrow-color": "#9aaba2", "target-arrow-shape": "triangle", "curve-style": "bezier" } },
        { selector: ":selected", style: { "background-color": "#b42318", "line-color": "#b42318", "target-arrow-color": "#b42318" } },
      ],
      layout: { name: "cose", animate: false, padding: 30 },
    });
    graph.on("tap", "edge", (event) => setSelected(String(event.target.data("explanation"))));
    return () => graph.destroy();
  }, [query.data]);
  if (query.isError) return <ApiErrorState error={query.error} retry={() => query.refetch()} />;
  return <div className="grid gap-6 xl:grid-cols-[1fr_320px]"><Card className="overflow-hidden"><CardHeader><CardTitle>Governed fraud-network projection</CardTitle></CardHeader><CardContent><div ref={container} className="h-[620px] rounded-xl border bg-slate-50" aria-label="Fraud indicator relationship graph" /></CardContent></Card><Card className="h-fit"><CardHeader><CardTitle>Relationship details</CardTitle></CardHeader><CardContent><p className="text-sm leading-6 text-slate-600">{selected}</p><p className="mt-5 text-xs leading-5 text-slate-500">Nodes represent ADRIS incidents and governed indicators. A connection is an investigative lead, not proof of common ownership or criminal conduct.</p></CardContent></Card></div>;
}
