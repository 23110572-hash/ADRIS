"use client";

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ArrowRight, Clock3, ListChecks, Network } from "lucide-react";
import Link from "next/link";
import { ApiErrorState } from "@/components/api-error";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getAnalystQueue } from "@/features/analyst/api";
import { useAnalystToken } from "@/features/analyst/access";

export function AnalystDashboard() {
  const token = useAnalystToken();
  const query = useQuery({ queryKey: ["analyst-queue"], queryFn: () => getAnalystQueue(token) });
  if (query.isError) return <ApiErrorState error={query.error} retry={() => query.refetch()} />;
  const items = query.data ?? [];
  const high = items.filter((item) => item.risk_band === "HIGH_RISK").length;
  const uncertain = items.filter((item) => item.risk_band === "UNABLE_TO_ASSESS" || item.risk_band === "CAUTION").length;
  return <div className="space-y-6"><div className="grid gap-4 sm:grid-cols-3"><Card><CardContent className="p-5"><ListChecks className="size-5 text-emerald-800" /><p className="mt-4 text-3xl font-black">{items.length}</p><p className="text-sm text-slate-600">Open review tasks</p></CardContent></Card><Card><CardContent className="p-5"><AlertTriangle className="size-5 text-red-700" /><p className="mt-4 text-3xl font-black">{high}</p><p className="text-sm text-slate-600">High-risk queue items</p></CardContent></Card><Card><CardContent className="p-5"><Clock3 className="size-5 text-amber-700" /><p className="mt-4 text-3xl font-black">{uncertain}</p><p className="text-sm text-slate-600">Caution or uncertain</p></CardContent></Card></div><Card><CardHeader><CardTitle>Priority work</CardTitle></CardHeader><CardContent className="space-y-3">{items.slice(0, 5).map((item) => <Link key={item.review_task_id} href={`/analyst/incidents/${item.incident_id}`} className="flex items-center justify-between gap-3 rounded-xl border p-4 hover:border-emerald-400"><div><div className="flex items-center gap-2"><Badge variant={item.risk_band === "HIGH_RISK" ? "danger" : "warning"}>{item.priority}</Badge><strong>Incident {item.incident_id.slice(0, 8)}</strong></div><p className="mt-1 line-clamp-1 text-sm text-slate-600">{item.reason}</p></div><ArrowRight className="size-4" /></Link>)}{!items.length && !query.isPending ? <p className="text-sm text-slate-600">No open review tasks.</p> : null}<div className="flex flex-wrap gap-3 pt-2"><Button asChild variant="outline"><Link href="/analyst/queue">Open full queue</Link></Button><Button asChild variant="outline"><Link href="/analyst/network"><Network /> Explore network</Link></Button></div></CardContent></Card></div>;
}
