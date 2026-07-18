import type { Metadata } from "next";
import { IncidentReview } from "@/features/analyst/incident-review";

export const metadata: Metadata = { title: "Analyst incident review" };

export default async function AnalystIncidentPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <IncidentReview incidentId={id} />;
}
