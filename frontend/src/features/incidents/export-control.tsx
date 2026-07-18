"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { Download, FileArchive, LoaderCircle } from "lucide-react";
import { useState } from "react";
import { ApiErrorState } from "@/components/api-error";
import { Button } from "@/components/ui/button";
import { createEvidenceExport, getExportDownload, getIncidentStatus } from "@/features/incidents/api";

export function ExportControl({ incidentId }: { incidentId: string }) {
  const [exportState, setExportState] = useState<{ exportId: string; jobId: string } | null>(null);
  const createMutation = useMutation({
    mutationFn: () => createEvidenceExport(incidentId),
    onSuccess: (result) => setExportState({ exportId: result.export.id, jobId: result.job_id }),
  });
  const statusQuery = useQuery({
    queryKey: ["export-status", incidentId, exportState?.jobId],
    queryFn: () => getIncidentStatus(incidentId),
    enabled: Boolean(exportState),
    refetchInterval: exportState ? 2_000 : false,
  });
  const exportJob = statusQuery.data?.jobs.find((job) => job.id === exportState?.jobId);
  const downloadMutation = useMutation({
    mutationFn: () => getExportDownload(incidentId, exportState!.exportId),
    onSuccess: ({ download_url }) => window.location.assign(download_url),
  });

  if (createMutation.isError) return <ApiErrorState error={createMutation.error} />;
  if (downloadMutation.isError) return <ApiErrorState error={downloadMutation.error} />;
  if (!exportState) return <Button variant="outline" onClick={() => createMutation.mutate()} disabled={createMutation.isPending}>{createMutation.isPending ? <LoaderCircle className="animate-spin" /> : <FileArchive />} Generate evidence package</Button>;
  if (exportJob?.status === "COMPLETED") return <Button onClick={() => downloadMutation.mutate()} disabled={downloadMutation.isPending}><Download /> Download private package</Button>;
  if (exportJob?.status === "FAILED") return <Button variant="outline" onClick={() => setExportState(null)}>Export failed — try again</Button>;
  return <Button variant="outline" disabled><LoaderCircle className="animate-spin" /> Building JSON and PDF…</Button>;
}
