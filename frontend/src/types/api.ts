import { z } from "zod";

const dateString = z.string();
const record = z.record(z.string(), z.unknown());

export const riskBandSchema = z.enum(["HIGH_RISK", "CAUTION", "NO_STRONG_SIGNAL", "UNABLE_TO_ASSESS"]);
export type RiskBand = z.infer<typeof riskBandSchema>;

export const incidentCreatedSchema = z.object({
  id: z.string().uuid(),
  status: z.string(),
  submission_type: z.string(),
  access_token: z.string().nullable().optional(),
  created_at: dateString,
  analysis_job_id: z.string().uuid().nullable().optional(),
});
export type IncidentCreated = z.infer<typeof incidentCreatedSchema>;

export const incidentSchema = z.object({
  id: z.string().uuid(),
  status: z.string(),
  submission_type: z.string(),
  language: z.string().nullable(),
  title: z.string().nullable(),
  input_quality: z.string(),
  district: z.string().nullable(),
  state: z.string().nullable(),
  preserved_at: dateString.nullable(),
  created_at: dateString,
  updated_at: dateString,
});
export type Incident = z.infer<typeof incidentSchema>;

export const jobSchema = z.object({
  id: z.string().uuid(),
  job_type: z.string(),
  status: z.string(),
  progress_percent: z.number(),
  progress_message: z.string().nullable(),
  error_code: z.string().nullable(),
  created_at: dateString,
  updated_at: dateString,
});
export type AnalysisJob = z.infer<typeof jobSchema>;

export const incidentStatusSchema = z.object({
  incident_id: z.string().uuid(),
  incident_status: z.string(),
  jobs: z.array(jobSchema),
  assessment_ready: z.boolean(),
});
export type IncidentStatus = z.infer<typeof incidentStatusSchema>;

export const assessmentSchema = z.object({
  id: z.string().uuid(),
  incident_id: z.string().uuid(),
  risk_band: riskBandSchema,
  policy_version: z.string(),
  reason_codes: z.array(z.string()),
  coverage: record,
  missing_sources: z.array(z.string()),
  agent_disagreement: z.boolean(),
  explanation: z.string(),
  safety_actions: z.array(z.string()),
  input_quality: z.string(),
  created_at: dateString,
});
export type Assessment = z.infer<typeof assessmentSchema>;

export const artifactSchema = z.object({
  id: z.string().uuid(),
  status: z.string(),
  original_filename: z.string(),
  expected_mime_type: z.string(),
  detected_mime_type: z.string().nullable(),
  size_bytes: z.number().nullable(),
  sha256: z.string().nullable(),
  receipt_at: dateString.nullable(),
  validated_at: dateString.nullable(),
  rejection_reason: z.string().nullable(),
  download_url: z.string().nullable().optional(),
});

export const derivativeSchema = z.object({
  id: z.string().uuid(),
  artifact_id: z.string().uuid(),
  kind: z.string(),
  provider: z.string(),
  provider_version: z.string(),
  mime_type: z.string(),
  sha256: z.string(),
  confidence: z.number().nullable(),
  source_reference: z.string(),
  download_url: z.string().nullable().optional(),
});

export const evidenceSchema = z.object({
  incident_id: z.string().uuid(),
  preserved_at: dateString.nullable(),
  artifacts: z.array(artifactSchema),
  derivatives: z.array(derivativeSchema),
  custody_events: z.array(record),
  limitation: z.string(),
});
export type Evidence = z.infer<typeof evidenceSchema>;

export const exportCreatedSchema = z.object({
  export: z.object({
    id: z.string().uuid(), incident_id: z.string().uuid(), status: z.string(), export_format: z.string(),
    sha256: z.string().nullable(), size_bytes: z.number().nullable(), created_at: dateString, completed_at: dateString.nullable(),
  }),
  job_id: z.string().uuid(),
});
export const downloadSchema = z.object({ download_url: z.string().url(), expires_in: z.number() });
export const preserveSchema = z.object({ incident_id: z.string().uuid(), manifest_id: z.string().uuid(), status: z.string() });

export const queueItemSchema = z.object({
  review_task_id: z.string().uuid(), incident_id: z.string().uuid(), priority: z.string(), status: z.string(), reason: z.string(),
  risk_band: z.string().nullable(), created_at: dateString,
});
export type QueueItem = z.infer<typeof queueItemSchema>;

const indicatorSchema = z.object({
  id: z.string().uuid(), indicator_type: z.string(), masked_value: z.string(), normalized_value: z.string(),
  normalized_value_hash: z.string(), confidence: z.number(), source_reference: z.string(), status: z.string(), reviewed: z.boolean(),
});
const signalSchema = z.object({
  id: z.string().uuid(), code: z.string(), family: z.string(), severity: z.number(), strength: z.string(), source: z.string(),
  evidence_reference: z.string(), explanation: z.string(), confidence: z.number(), status: z.string(),
});
const agentRunSchema = z.object({
  id: z.string().uuid(), agent_name: z.string(), status: z.string(), model_provider: z.string(), model_name: z.string().nullable(),
  prompt_version: z.string(), agent_version: z.string(), tool_versions: record, latency_ms: z.number().nullable(),
  input_tokens: z.number().nullable(), output_tokens: z.number().nullable(), error_code: z.string().nullable(), created_at: dateString,
});
const reviewSchema = z.object({
  id: z.string().uuid(), incident_id: z.string().uuid(), review_task_id: z.string().uuid(), disposition: z.string(), status: z.string(), created_at: dateString,
});
export const analystIncidentSchema = z.object({
  incident: incidentSchema,
  artifacts: z.array(artifactSchema),
  derivatives: z.array(derivativeSchema),
  indicators: z.array(indicatorSchema),
  signals: z.array(signalSchema),
  assessments: z.array(assessmentSchema),
  agent_runs: z.array(agentRunSchema),
  reviews: z.array(reviewSchema),
});
export type AnalystIncident = z.infer<typeof analystIncidentSchema>;

export const graphSchema = z.object({
  nodes: z.array(z.object({ id: z.string(), label: z.string(), entity_type: z.string(), occurrence_count: z.number(), risk_band: z.string().nullable().optional() })),
  edges: z.array(z.object({ id: z.string(), source: z.string(), target: z.string(), relationship_type: z.string(), explanation: z.string(), weight: z.number() })),
  generated_at: dateString,
});
export type GraphData = z.infer<typeof graphSchema>;

export const mapSchema = z.object({
  cells: z.array(z.object({
    h3_cell: z.string(), latitude: z.number(), longitude: z.number(), incident_count: z.number(), high_risk_count: z.number(),
    caution_count: z.number(), trend_ratio: z.number().nullable(), period_start: dateString, period_end: dateString,
  })),
  minimum_display_count: z.number(), privacy_note: z.string(), generated_at: dateString,
});
export type MapData = z.infer<typeof mapSchema>;

export const reviewListSchema = z.array(reviewSchema);
export const exportListSchema = z.array(z.object({
  id: z.string().uuid(), incident_id: z.string().uuid(), status: z.string(), export_format: z.string(), sha256: z.string().nullable(),
  size_bytes: z.number().nullable(), created_at: dateString, completed_at: dateString.nullable(),
}));
