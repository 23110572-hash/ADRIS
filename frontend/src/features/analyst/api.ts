import { z } from "zod";
import { apiRequest } from "@/lib/api";
import {
  analystIncidentSchema,
  exportListSchema,
  graphSchema,
  mapSchema,
  queueItemSchema,
  reviewListSchema,
} from "@/types/api";

export const getAnalystQueue = (token: string) => apiRequest("/v1/analyst/queue", z.array(queueItemSchema), {}, token);
export const getAnalystIncident = (id: string, token: string) => apiRequest(`/v1/analyst/incidents/${id}`, analystIncidentSchema, {}, token);
export const getNetwork = (token: string) => apiRequest("/v1/analyst/network", graphSchema, {}, token);
export const getMapData = (token: string) => apiRequest("/v1/analyst/map", mapSchema, {}, token);
export const getReviews = (token: string) => apiRequest("/v1/analyst/reviews", reviewListSchema, {}, token);
export const getExports = (token: string) => apiRequest("/v1/analyst/exports", exportListSchema, {}, token);

export const submitReview = (incidentId: string, token: string, payload: {
  review_task_id: string;
  disposition: "CONFIRMED_PATTERN" | "PLAUSIBLE" | "INSUFFICIENT" | "LEGITIMATE" | "MALICIOUS_SUBMISSION";
  notes?: string;
  reason_codes: string[];
}) => apiRequest(
  `/v1/analyst/incidents/${incidentId}/review`,
  z.object({ id: z.string().uuid(), incident_id: z.string().uuid(), review_task_id: z.string().uuid(), disposition: z.string(), status: z.string(), created_at: z.string() }),
  { method: "POST", body: JSON.stringify(payload) },
  token,
);

export const submitCorrection = (incidentId: string, token: string, payload: Record<string, unknown>) => apiRequest(
  `/v1/analyst/incidents/${incidentId}/corrections`,
  z.object({ id: z.string().uuid(), status: z.string() }),
  { method: "POST", body: JSON.stringify(payload) },
  token,
);
