import type { Metadata } from "next";
import { PageShell } from "@/components/page-shell";
import { ResultView } from "@/features/incidents/result-view";

export const metadata: Metadata = { title: "Risk result" };
export default async function IncidentResultPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <PageShell eyebrow={`Incident ${id.slice(0, 8)}`} title="Risk assessment" description="The final band is assigned by the versioned ADRIS policy—not by an LLM."><ResultView incidentId={id} /></PageShell>;
}
