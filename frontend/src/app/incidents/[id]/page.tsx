import type { Metadata } from "next";
import { PageShell } from "@/components/page-shell";
import { IncidentStatusView } from "@/features/incidents/status-view";

export const metadata: Metadata = { title: "Incident processing" };
export default async function IncidentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <PageShell eyebrow={`Incident ${id.slice(0, 8)}`} title="Your submission is being checked" description="The incident is already stored. Slow analysis or a Redis outage will not erase the durable record."><IncidentStatusView incidentId={id} /></PageShell>;
}
