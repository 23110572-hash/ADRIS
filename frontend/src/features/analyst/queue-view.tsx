"use client";

import { useQuery } from "@tanstack/react-query";
import { ArrowRight } from "lucide-react";
import Link from "next/link";
import { ApiErrorState } from "@/components/api-error";
import { EmptyState } from "@/components/empty-state";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getAnalystQueue } from "@/features/analyst/api";
import { useAnalystToken } from "@/features/analyst/access";

export function QueueView() {
  const token = useAnalystToken();
  const query = useQuery({ queryKey: ["analyst-queue"], queryFn: () => getAnalystQueue(token), refetchInterval: 15_000 });
  if (query.isError) return <ApiErrorState error={query.error} retry={() => query.refetch()} />;
  const queue = query.data ?? [];
  return <Card><CardHeader><CardTitle>Human review queue</CardTitle></CardHeader><CardContent>{!queue.length && !query.isPending ? <EmptyState title="Queue clear" description="New high-risk, uncertain, conflicting, and escalated incidents will appear here." /> : <div className="overflow-x-auto"><table className="w-full min-w-[760px] text-left text-sm"><thead><tr className="border-b text-xs uppercase tracking-wide text-slate-500"><th className="px-3 py-3">Priority</th><th className="px-3 py-3">Incident</th><th className="px-3 py-3">Risk</th><th className="px-3 py-3">Reason</th><th className="px-3 py-3">Age</th><th /></tr></thead><tbody>{queue.map((item) => <tr key={item.review_task_id} className="border-b last:border-0"><td className="px-3 py-4"><Badge variant={item.priority === "P1" ? "danger" : "warning"}>{item.priority}</Badge></td><td className="px-3 py-4 font-mono text-xs">{item.incident_id.slice(0, 12)}</td><td className="px-3 py-4">{item.risk_band?.replaceAll("_", " ") ?? "Pending"}</td><td className="max-w-md px-3 py-4 text-slate-600">{item.reason}</td><td className="px-3 py-4 text-slate-500">{new Date(item.created_at).toLocaleString()}</td><td className="px-3 py-4"><Link href={`/analyst/incidents/${item.incident_id}`} aria-label="Review incident"><ArrowRight className="size-4" /></Link></td></tr>)}</tbody></table></div>}</CardContent></Card>;
}
