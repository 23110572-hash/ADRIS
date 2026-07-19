"use client";

import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, CircleDashed, Clock3, ShieldAlert, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { ApiErrorState } from "@/components/api-error";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { getIncidentStatus } from "@/features/incidents/api";

const labels: Record<string, string> = {
  FILE_VALIDATION: "Validate and seal original",
  OCR: "Extract text and image metadata",
  TRANSCRIPTION: "Transcribe consented audio",
  AGENT_ANALYSIS: "Run bounded risk analysis",
  AGENT_RETRY: "Retry unavailable AI analysis",
  GRAPH_ANALYSIS: "Project governed indicator links",
  EVIDENCE_EXPORT: "Generate evidence package",
};

export function IncidentStatusView({ incidentId }: { incidentId: string }) {
  const router = useRouter();
  const query = useQuery({
    queryKey: ["incident-status", incidentId],
    queryFn: () => getIncidentStatus(incidentId),
    refetchInterval: 2_500,
  });
  useEffect(() => {
    if (query.data?.assessment_ready) router.replace(`/incidents/${incidentId}/result`);
  }, [incidentId, query.data?.assessment_ready, router]);

  if (query.isError) return <ApiErrorState error={query.error} retry={() => query.refetch()} />;
  const jobs = query.data?.jobs ?? [];
  const active = jobs.find((job) => ["PENDING", "RUNNING"].includes(job.status));
  const progress = active?.progress_percent ?? (jobs.some((job) => job.status === "COMPLETED") ? 85 : 10);
  const analysisFailed =
    !query.data?.assessment_ready &&
    !active &&
    jobs.some((job) => job.status === "FAILED" && ["AGENT_ANALYSIS", "AGENT_RETRY"].includes(job.job_type));
  return (
    <div className="grid gap-6 lg:grid-cols-[1fr_320px]">
      {analysisFailed ? (
        <Card className="border-red-200">
          <CardHeader><CardTitle className="flex items-center gap-2 text-red-800"><ShieldAlert className="size-5" /> AI analysis could not complete</CardTitle></CardHeader>
          <CardContent className="space-y-4 text-sm leading-6 text-slate-700">
            <p>ADRIS assesses submissions with its AI agents and does not produce a risk result without them. Your incident and evidence remain safely preserved.</p>
            <p>Please try again shortly. If you feel unsafe right now, open the urgent guidance immediately.</p>
            <div className="flex flex-wrap gap-2">
              <Button onClick={() => query.refetch()}>Retry check</Button>
              <Button asChild variant="outline"><Link href="/emergency">Open urgent guidance</Link></Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        <Card>
          <CardHeader><CardTitle className="flex items-center gap-2"><CircleDashed className="size-5 animate-spin text-emerald-700" /> Checking your submission</CardTitle></CardHeader>
          <CardContent className="space-y-6">
            <div><div className="mb-2 flex justify-between text-sm"><span>{active?.progress_message ?? "Waiting for durable processing"}</span><span>{progress}%</span></div><Progress value={progress} /></div>
            <ol className="space-y-3">
              {jobs.length ? jobs.map((job) => (
                <li key={job.id} className="flex gap-3 rounded-xl border p-4">
                  {job.status === "COMPLETED" ? <CheckCircle2 className="mt-0.5 size-5 text-emerald-700" /> : <Clock3 className="mt-0.5 size-5 text-amber-700" />}
                  <div className="min-w-0 flex-1"><div className="flex flex-wrap items-center justify-between gap-2"><strong>{labels[job.job_type] ?? job.job_type}</strong><Badge variant={job.status === "COMPLETED" ? "success" : job.status === "FAILED" ? "danger" : "warning"}>{job.status}</Badge></div><p className="mt-1 text-sm text-slate-600">{job.progress_message ?? "Queued from the permanent incident record"}</p>{job.error_code ? <p className="mt-1 text-xs text-red-700">Declared gap: {job.error_code}</p> : null}</div>
                </li>
              )) : <li className="rounded-xl border border-dashed p-5 text-sm text-slate-600">The incident is stored. Redis processing may be delayed; reconciliation will retry pending work.</li>}
            </ol>
            {query.data?.assessment_ready ? <Button onClick={() => router.push(`/incidents/${incidentId}/result`)}>View result</Button> : null}
          </CardContent>
        </Card>
      )}
      <Card className="h-fit border-emerald-200 bg-emerald-50">
        <CardHeader><CardTitle className="flex items-center gap-2 text-emerald-950"><ShieldCheck className="size-5" /> While you wait</CardTitle></CardHeader>
        <CardContent className="space-y-3 text-sm leading-6 text-emerald-950"><p><strong>Do not transfer money</strong> to prove innocence or verify an account.</p><p>Do not share an OTP, PIN, password, CVV, or screen access.</p><p>ADRIS assesses your submission with AI agents. If AI is briefly unavailable it retries and never guesses a result.</p><Button asChild variant="outline"><Link href="/emergency">Open urgent guidance</Link></Button></CardContent>
      </Card>
    </div>
  );
}
