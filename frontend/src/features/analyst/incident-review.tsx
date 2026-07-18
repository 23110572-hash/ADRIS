"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Download, Edit3, LoaderCircle } from "lucide-react";
import { useState } from "react";
import { ApiErrorState } from "@/components/api-error";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { getAnalystIncident, getAnalystQueue, submitCorrection, submitReview } from "@/features/analyst/api";
import { useAnalystToken } from "@/features/analyst/access";

const dispositions = ["CONFIRMED_PATTERN", "PLAUSIBLE", "INSUFFICIENT", "LEGITIMATE", "MALICIOUS_SUBMISSION"] as const;

export function IncidentReview({ incidentId }: { incidentId: string }) {
  const token = useAnalystToken();
  const client = useQueryClient();
  const [disposition, setDisposition] = useState<(typeof dispositions)[number]>("PLAUSIBLE");
  const [notes, setNotes] = useState("");
  const incidentQuery = useQuery({ queryKey: ["analyst-incident", incidentId], queryFn: () => getAnalystIncident(incidentId, token) });
  const queueQuery = useQuery({ queryKey: ["analyst-queue"], queryFn: () => getAnalystQueue(token) });
  const task = queueQuery.data?.find((item) => item.incident_id === incidentId);
  const reviewMutation = useMutation({ mutationFn: () => {
    if (!task) throw new Error("No open review task exists for this incident.");
    return submitReview(incidentId, token, { review_task_id: task.review_task_id, disposition, notes, reason_codes: [] });
  }, onSuccess: () => { client.invalidateQueries({ queryKey: ["analyst-incident", incidentId] }); client.invalidateQueries({ queryKey: ["analyst-queue"] }); } });
  const correctionMutation = useMutation({ mutationFn: (payload: Record<string, unknown>) => submitCorrection(incidentId, token, payload), onSuccess: () => client.invalidateQueries({ queryKey: ["analyst-incident", incidentId] }) });
  if (incidentQuery.isError) return <ApiErrorState error={incidentQuery.error} retry={() => incidentQuery.refetch()} />;
  if (!incidentQuery.data) return <Card><CardContent className="p-8"><LoaderCircle className="animate-spin" /></CardContent></Card>;
  const data = incidentQuery.data;
  const current = data.assessments.find((item) => item.id) ?? null;
  return <div className="space-y-6">
    <div className="grid gap-4 sm:grid-cols-4"><Card><CardContent className="p-4"><p className="text-xs text-slate-500">Incident</p><p className="mt-1 font-mono text-sm">{incidentId.slice(0, 12)}</p></CardContent></Card><Card><CardContent className="p-4"><p className="text-xs text-slate-500">Risk band</p><Badge className="mt-1" variant={current?.risk_band === "HIGH_RISK" ? "danger" : "warning"}>{current?.risk_band ?? "PENDING"}</Badge></CardContent></Card><Card><CardContent className="p-4"><p className="text-xs text-slate-500">Signals</p><p className="mt-1 text-xl font-black">{data.signals.length}</p></CardContent></Card><Card><CardContent className="p-4"><p className="text-xs text-slate-500">Indicators</p><p className="mt-1 text-xl font-black">{data.indicators.length}</p></CardContent></Card></div>
    <div className="grid gap-6 xl:grid-cols-[1.2fr_.8fr]"><div className="space-y-6"><Card><CardHeader><CardTitle>Exact risk reasons</CardTitle></CardHeader><CardContent className="space-y-3">{data.signals.map((signal) => <article key={signal.id} className="rounded-xl border p-4"><div className="flex flex-wrap justify-between gap-2"><strong>{signal.code.replaceAll("_", " ")}</strong><Badge variant={signal.strength === "STRONG" ? "danger" : "warning"}>{signal.strength} · {signal.confidence.toFixed(2)}</Badge></div><p className="mt-2 text-sm text-slate-600">{signal.explanation}</p><code className="mt-2 block text-xs text-slate-500">{signal.evidence_reference}</code><Button size="sm" variant="ghost" className="mt-2" onClick={() => correctionMutation.mutate({ signal_id: signal.id, field_name: "status", corrected_value: "INACTIVE", reason: "Analyst marked this classification as incorrect" })}><Edit3 /> Mark incorrect</Button></article>)}</CardContent></Card><Card><CardHeader><CardTitle>Extracted indicators</CardTitle></CardHeader><CardContent className="overflow-x-auto"><table className="w-full min-w-[650px] text-left text-sm"><thead><tr className="border-b text-xs text-slate-500"><th className="p-2">Type</th><th className="p-2">Value</th><th className="p-2">Confidence</th><th className="p-2">Source</th><th /></tr></thead><tbody>{data.indicators.map((item) => <tr key={item.id} className="border-b"><td className="p-2 font-semibold">{item.indicator_type}</td><td className="p-2 font-mono text-xs">{item.normalized_value}</td><td className="p-2">{item.confidence.toFixed(2)}</td><td className="p-2 text-xs">{item.source_reference}</td><td className="p-2"><Button size="sm" variant="ghost" onClick={() => correctionMutation.mutate({ indicator_id: item.id, field_name: "status", corrected_value: "INACTIVE", reason: "Analyst marked this extraction as incorrect" })}>Correct</Button></td></tr>)}</tbody></table></CardContent></Card><Card><CardHeader><CardTitle>Evidence objects</CardTitle></CardHeader><CardContent className="grid gap-3 sm:grid-cols-2">{[...data.artifacts, ...data.derivatives].map((item) => <a key={item.id} href={item.download_url ?? undefined} target="_blank" rel="noreferrer" className="rounded-xl border p-4 hover:border-emerald-400"><Download className="size-4" /><strong className="mt-2 block">{"original_filename" in item ? item.original_filename : item.kind}</strong><code className="mt-1 block break-all text-[10px] text-slate-500">{item.sha256 ?? "hash pending"}</code></a>)}</CardContent></Card></div>
      <aside className="space-y-6"><Card><CardHeader><CardTitle>Record disposition</CardTitle></CardHeader><CardContent className="space-y-4"><div className="space-y-2"><Label htmlFor="disposition">Disposition</Label><select id="disposition" value={disposition} onChange={(event) => setDisposition(event.target.value as typeof disposition)} className="h-11 w-full rounded-xl border bg-white px-3 text-sm">{dispositions.map((value) => <option key={value}>{value}</option>)}</select></div><div className="space-y-2"><Label htmlFor="review-notes">Review notes</Label><Textarea id="review-notes" value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="Record evidence-based observations and limitations." /></div>{reviewMutation.isError ? <ApiErrorState error={reviewMutation.error} /> : null}<Button onClick={() => reviewMutation.mutate()} disabled={!task || reviewMutation.isPending}>{reviewMutation.isPending ? <LoaderCircle className="animate-spin" /> : <Check />} {task ? "Complete review" : "No open task"}</Button></CardContent></Card><Card><CardHeader><CardTitle>Version provenance</CardTitle></CardHeader><CardContent className="space-y-3">{data.agent_runs.map((run) => <div key={run.id} className="rounded-xl bg-slate-50 p-3 text-xs"><div className="flex justify-between"><strong>{run.agent_name}</strong><Badge variant={run.status === "COMPLETED" ? "success" : "warning"}>{run.status}</Badge></div><dl className="mt-2 grid grid-cols-[90px_1fr] gap-1 text-slate-600"><dt>Model</dt><dd>{run.model_name ?? run.model_provider}</dd><dt>Prompt</dt><dd>{run.prompt_version}</dd><dt>Agent</dt><dd>{run.agent_version}</dd></dl></div>)}</CardContent></Card></aside></div>
  </div>;
}
