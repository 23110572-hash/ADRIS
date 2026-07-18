"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { AlertOctagon, CheckCircle2, CircleHelp, FileLock2, ShieldAlert, TriangleAlert } from "lucide-react";
import Link from "next/link";
import { ApiErrorState } from "@/components/api-error";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ExportControl } from "@/features/incidents/export-control";
import { getAssessment, preserveIncident } from "@/features/incidents/api";
import type { RiskBand } from "@/types/api";

const presentation: Record<RiskBand, { title: string; icon: typeof AlertOctagon; className: string; badge: "danger" | "warning" | "success" | "outline" }> = {
  HIGH_RISK: { title: "High-risk signals detected", icon: AlertOctagon, className: "border-red-300 bg-red-50 text-red-950", badge: "danger" },
  CAUTION: { title: "Use caution and verify independently", icon: TriangleAlert, className: "border-amber-300 bg-amber-50 text-amber-950", badge: "warning" },
  NO_STRONG_SIGNAL: { title: "No strong signal detected", icon: CheckCircle2, className: "border-emerald-300 bg-emerald-50 text-emerald-950", badge: "success" },
  UNABLE_TO_ASSESS: { title: "Unable to assess reliably", icon: CircleHelp, className: "border-slate-300 bg-slate-50 text-slate-950", badge: "outline" },
};

export function ResultView({ incidentId }: { incidentId: string }) {
  const query = useQuery({ queryKey: ["assessment", incidentId], queryFn: () => getAssessment(incidentId) });
  const preserve = useMutation({ mutationFn: () => preserveIncident(incidentId) });
  if (query.isPending) return <Card><CardContent className="p-8 text-sm text-slate-600">Loading the signed policy result…</CardContent></Card>;
  if (query.isError) return <ApiErrorState error={query.error} retry={() => query.refetch()} />;
  const assessment = query.data;
  const view = presentation[assessment.risk_band];
  const Icon = view.icon;
  return (
    <div className="space-y-6">
      <section className={`rounded-3xl border p-6 sm:p-8 ${view.className}`}>
        <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
          <div><Icon className="size-10" /><h2 className="mt-4 text-2xl font-black sm:text-3xl">{view.title}</h2><p className="mt-3 max-w-3xl text-base leading-7">{assessment.explanation}</p></div>
          <Badge variant={view.badge} className="w-fit text-sm">{assessment.risk_band.replaceAll("_", " ")}</Badge>
        </div>
        {assessment.risk_band === "NO_STRONG_SIGNAL" ? <p className="mt-5 rounded-xl border border-emerald-300 bg-white/70 p-4 text-sm font-bold">This result does not prove that the interaction, person, payment request, or link is legitimate.</p> : null}
      </section>
      <div className="grid gap-6 lg:grid-cols-2">
        <Card><CardHeader><CardTitle>Why ADRIS returned this result</CardTitle></CardHeader><CardContent><ul className="space-y-3">{assessment.reason_codes.map((reason) => <li key={reason} className="flex gap-3 rounded-xl bg-slate-50 p-3 text-sm"><ShieldAlert className="mt-0.5 size-4 shrink-0 text-emerald-800" /><span>{reason.replaceAll("_", " ").toLowerCase()}</span></li>)}</ul><div className="mt-5 flex flex-wrap gap-2 text-xs"><Badge variant="outline">Policy {assessment.policy_version}</Badge><Badge variant="outline">Quality {assessment.input_quality}</Badge>{assessment.agent_disagreement ? <Badge variant="warning">Agent disagreement</Badge> : null}</div></CardContent></Card>
        <Card><CardHeader><CardTitle>Act safely now</CardTitle></CardHeader><CardContent><ol className="space-y-3">{assessment.safety_actions.map((action, index) => <li key={action} className="flex gap-3 text-sm leading-6"><span className="grid size-7 shrink-0 place-items-center rounded-full bg-emerald-800 text-xs font-bold text-white">{index + 1}</span><span>{action}</span></li>)}</ol></CardContent></Card>
      </div>
      {assessment.missing_sources.length ? <Card className="border-amber-200"><CardHeader><CardTitle>What ADRIS could not check</CardTitle></CardHeader><CardContent><ul className="list-disc space-y-1 pl-5 text-sm text-slate-700">{assessment.missing_sources.map((source) => <li key={source}>{source.replaceAll("_", " ")}</li>)}</ul></CardContent></Card> : null}
      <Card><CardHeader><CardTitle className="flex items-center gap-2"><FileLock2 className="size-5" /> Preserve and report</CardTitle></CardHeader><CardContent className="flex flex-wrap gap-3"><Button onClick={() => preserve.mutate()} disabled={preserve.isPending || preserve.isSuccess}>{preserve.isSuccess ? "Evidence preserved" : preserve.isPending ? "Sealing manifest…" : "Preserve evidence"}</Button><ExportControl incidentId={incidentId} /><Button asChild variant="outline"><Link href={`/incidents/${incidentId}/evidence`}>Review evidence</Link></Button><Button asChild variant="destructive"><Link href="/reporting">Reporting guidance</Link></Button></CardContent>{preserve.isError ? <CardContent><ApiErrorState error={preserve.error} /></CardContent> : null}</Card>
    </div>
  );
}
