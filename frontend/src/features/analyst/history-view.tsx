"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { ApiErrorState } from "@/components/api-error";
import { EmptyState } from "@/components/empty-state";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getExports, getReviews } from "@/features/analyst/api";
import { useAnalystToken } from "@/features/analyst/access";

export function ReviewsHistory() {
  const token = useAnalystToken(); const query = useQuery({ queryKey: ["analyst-reviews"], queryFn: () => getReviews(token) });
  if (query.isError) return <ApiErrorState error={query.error} retry={() => query.refetch()} />;
  return <Card><CardHeader><CardTitle>Completed review dispositions</CardTitle></CardHeader><CardContent>{query.data?.length ? <div className="space-y-3">{query.data.map((item) => <Link key={item.id} href={`/analyst/incidents/${item.incident_id}`} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border p-4 hover:border-emerald-400"><div><strong>Incident {item.incident_id.slice(0, 8)}</strong><p className="mt-1 text-xs text-slate-500">{new Date(item.created_at).toLocaleString()}</p></div><Badge variant="success">{item.disposition.replaceAll("_", " ")}</Badge></Link>)}</div> : <EmptyState title="No completed reviews" description="Analyst dispositions will appear here with their incident audit trail." />}</CardContent></Card>;
}

export function ExportsHistory() {
  const token = useAnalystToken(); const query = useQuery({ queryKey: ["analyst-exports"], queryFn: () => getExports(token), refetchInterval: 10_000 });
  if (query.isError) return <ApiErrorState error={query.error} retry={() => query.refetch()} />;
  return <Card><CardHeader><CardTitle>Evidence package exports</CardTitle></CardHeader><CardContent>{query.data?.length ? <div className="overflow-x-auto"><table className="w-full min-w-[700px] text-left text-sm"><thead><tr className="border-b text-xs text-slate-500"><th className="p-3">Incident</th><th className="p-3">Status</th><th className="p-3">Format</th><th className="p-3">SHA-256</th><th className="p-3">Created</th></tr></thead><tbody>{query.data.map((item) => <tr key={item.id} className="border-b"><td className="p-3"><Link className="font-mono text-xs text-emerald-800" href={`/analyst/incidents/${item.incident_id}`}>{item.incident_id.slice(0, 12)}</Link></td><td className="p-3"><Badge variant={item.status === "COMPLETED" ? "success" : item.status === "FAILED" ? "danger" : "warning"}>{item.status}</Badge></td><td className="p-3">{item.export_format}</td><td className="max-w-xs break-all p-3 font-mono text-[10px]">{item.sha256 ?? "pending"}</td><td className="p-3 text-xs">{new Date(item.created_at).toLocaleString()}</td></tr>)}</tbody></table></div> : <EmptyState title="No exports generated" description="Generated JSON manifests and PDF chronology packages will be recorded here." />}</CardContent></Card>;
}
