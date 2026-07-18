import { z } from "zod";
import { apiRequest, createIdempotencyKey, incidentHeaders, storeIncidentToken } from "@/lib/api";
import {
  assessmentSchema,
  downloadSchema,
  evidenceSchema,
  exportCreatedSchema,
  incidentCreatedSchema,
  incidentSchema,
  incidentStatusSchema,
  preserveSchema,
} from "@/types/api";

export type SubmissionType = "MESSAGE" | "SCREENSHOT" | "DOCUMENT" | "URL" | "QR" | "AUDIO";

export async function createIncident(input: {
  submission_type: SubmissionType;
  text?: string;
  language?: string;
  title?: string;
  consent_confirmed?: boolean;
}) {
  const result = await apiRequest("/v1/incidents", incidentCreatedSchema, {
    method: "POST",
    headers: { "Idempotency-Key": createIdempotencyKey("create") },
    body: JSON.stringify(input),
  });
  storeIncidentToken(result.id, result.access_token);
  return result;
}

export async function uploadIncidentFile(input: {
  submissionType: Exclude<SubmissionType, "MESSAGE" | "URL">;
  file: File;
  consentConfirmed?: boolean;
}) {
  const incident = await createIncident({
    submission_type: input.submissionType,
    title: input.file.name,
    consent_confirmed: input.consentConfirmed ?? true,
  });
  const presign = await apiRequest(
    `/v1/incidents/${incident.id}/uploads/presign`,
    z.object({ artifact_id: z.string().uuid(), upload_url: z.string().url(), method: z.literal("PUT"), headers: z.record(z.string(), z.string()), expires_in: z.number() }),
    {
      method: "POST",
      headers: incidentHeaders(incident.id),
      body: JSON.stringify({ filename: input.file.name, content_type: input.file.type, size_bytes: input.file.size }),
    },
  );
  const upload = await fetch(presign.upload_url, { method: "PUT", headers: presign.headers, body: input.file });
  if (!upload.ok) throw new Error(`Private upload failed (${upload.status})`);
  await apiRequest(
    `/v1/incidents/${incident.id}/uploads/complete`,
    z.object({ artifact_id: z.string().uuid(), status: z.string(), validation_job_id: z.string().uuid() }),
    {
      method: "POST",
      headers: incidentHeaders(incident.id),
      body: JSON.stringify({ artifact_id: presign.artifact_id }),
    },
  );
  return incident;
}

export const getIncident = (id: string) => apiRequest(`/v1/incidents/${id}`, incidentSchema, { headers: incidentHeaders(id) });
export const getIncidentStatus = (id: string) => apiRequest(`/v1/incidents/${id}/status`, incidentStatusSchema, { headers: incidentHeaders(id) });
export const getAssessment = (id: string) => apiRequest(`/v1/incidents/${id}/assessment`, assessmentSchema, { headers: incidentHeaders(id) });
export const getEvidence = (id: string) => apiRequest(`/v1/incidents/${id}/evidence`, evidenceSchema, { headers: incidentHeaders(id) });

export const preserveIncident = (id: string) => apiRequest(
  `/v1/incidents/${id}/preserve`, preserveSchema,
  { method: "POST", headers: incidentHeaders(id, { "Idempotency-Key": createIdempotencyKey("preserve") }) },
);

export const createEvidenceExport = (id: string) => apiRequest(
  `/v1/incidents/${id}/exports`, exportCreatedSchema,
  {
    method: "POST",
    headers: incidentHeaders(id, { "Idempotency-Key": createIdempotencyKey("export") }),
    body: JSON.stringify({ export_format: "ZIP" }),
  },
);

export const getExportDownload = (id: string, exportId: string) => apiRequest(
  `/v1/exports/${exportId}/download`, downloadSchema, { headers: incidentHeaders(id) },
);
