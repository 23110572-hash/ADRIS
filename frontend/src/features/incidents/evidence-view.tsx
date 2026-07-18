"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Download, FileCheck2, FileText, Fingerprint } from "lucide-react";
import { ApiErrorState } from "@/components/api-error";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getEvidence, preserveIncident } from "@/features/incidents/api";

export function EvidenceView({ incidentId }: { incidentId: string }) {
  const query = useQuery({ queryKey: ["evidence", incidentId], queryFn: () => getEvidence(incidentId) });
  const preserve = useMutation({ mutationFn: () => preserveIncident(incidentId), onSuccess: () => query.refetch() });
  if (query.isPending) return <Card><CardContent className="p-8 text-sm text-slate-600">Opening audited evidence inventory…</CardContent></Card>;
  if (query.isError) return <ApiErrorState error={query.error} retry={() => query.refetch()} />;
  const evidence = query.data;
  return (
    <div className="space-y-6">
      <Card className="border-emerald-200"><CardContent className="flex flex-col gap-4 p-5 sm:flex-row sm:items-center sm:justify-between"><div><strong className="block">Preservation status</strong><span className="text-sm text-slate-600">{evidence.preserved_at ? `Sealed ${new Date(evidence.preserved_at).toLocaleString()}` : "Not yet sealed into a manifest"}</span></div><Button onClick={() => preserve.mutate()} disabled={preserve.isPending || Boolean(evidence.preserved_at)}><FileCheck2 /> {evidence.preserved_at ? "Preserved" : preserve.isPending ? "Preserving…" : "Preserve now"}</Button></CardContent></Card>
      {preserve.isError ? <ApiErrorState error={preserve.error} /> : null}
      <Card><CardHeader><CardTitle>Original artifact inventory</CardTitle></CardHeader><CardContent className="space-y-3">{evidence.artifacts.length ? evidence.artifacts.map((artifact) => <article key={artifact.id} className="rounded-xl border p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-bold">{artifact.original_filename}</h3><p className="mt-1 text-xs text-slate-500">{artifact.detected_mime_type ?? artifact.expected_mime_type} · {artifact.size_bytes ? `${(artifact.size_bytes / 1024).toFixed(1)} KB` : "size pending"}</p></div><Badge variant={artifact.status === "ACCEPTED" ? "success" : artifact.status === "REJECTED" ? "danger" : "warning"}>{artifact.status}</Badge></div><div className="mt-3 flex items-start gap-2 rounded-lg bg-slate-950 p-3 text-xs text-slate-100"><Fingerprint className="mt-0.5 size-4 shrink-0" /><code className="break-all">SHA-256: {artifact.sha256 ?? "pending validation"}</code></div>{artifact.download_url ? <Button asChild size="sm" variant="outline" className="mt-3"><a href={artifact.download_url} target="_blank" rel="noreferrer"><Download /> Open private original</a></Button> : null}</article>) : <p className="text-sm text-slate-600">This incident contains submitted text and no uploaded original artifact.</p>}</CardContent></Card>
      <Card><CardHeader><CardTitle>Derived evidence</CardTitle></CardHeader><CardContent className="grid gap-3 sm:grid-cols-2">{evidence.derivatives.length ? evidence.derivatives.map((item) => <article key={item.id} className="rounded-xl border p-4"><FileText className="size-5 text-emerald-800" /><h3 className="mt-2 font-bold">{item.kind.replaceAll("_", " ")}</h3><p className="mt-1 text-xs text-slate-500">{item.provider} {item.provider_version} · confidence {item.confidence?.toFixed(2) ?? "not available"}</p><code className="mt-3 block break-all rounded-lg bg-slate-100 p-2 text-[11px]">{item.sha256}</code>{item.download_url ? <Button asChild size="sm" variant="outline" className="mt-3"><a href={item.download_url} target="_blank" rel="noreferrer"><Download /> Open derivative</a></Button> : null}</article>) : <p className="text-sm text-slate-600">No derivatives are available yet.</p>}</CardContent></Card>
      <Card><CardHeader><CardTitle>Custody timeline</CardTitle></CardHeader><CardContent><ol className="border-l-2 border-emerald-200 pl-5">{evidence.custody_events.map((event, index) => <li key={`${String(event.event_type)}-${index}`} className="relative pb-5 text-sm before:absolute before:-left-[27px] before:top-1 before:size-3 before:rounded-full before:bg-emerald-700"><strong>{String(event.event_type).replaceAll("_", " ")}</strong><p className="mt-1 break-all text-xs text-slate-500">Payload hash: {String(event.payload_hash ?? "recorded")}</p></li>)}</ol><p className="mt-3 text-xs leading-5 text-slate-500">{evidence.limitation}</p></CardContent></Card>
    </div>
  );
}
