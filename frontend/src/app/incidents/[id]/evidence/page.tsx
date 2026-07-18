import type { Metadata } from "next";
import { PageShell } from "@/components/page-shell";
import { EvidenceView } from "@/features/incidents/evidence-view";

export const metadata: Metadata = { title: "Evidence inventory" };
export default async function IncidentEvidencePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <PageShell eyebrow={`Incident ${id.slice(0, 8)}`} title="Evidence and preservation" description="Review private originals, deterministic hashes, derivatives, and custody events. Every evidence access is audited."><EvidenceView incidentId={id} /></PageShell>;
}
