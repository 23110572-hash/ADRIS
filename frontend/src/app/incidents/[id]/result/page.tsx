import type { Metadata } from "next";
import { PageShell } from "@/components/page-shell";
import { ResultView } from "@/features/incidents/result-view";

export const metadata: Metadata = { title: "Scam Check Result" };
export default async function IncidentResultPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <PageShell
      eyebrow={`Check Reference #${id.slice(0, 8)}`}
      title="Scam Safety Check Result"
      description="Here is what our safety check found about the message or file you submitted."
    >
      <ResultView incidentId={id} />
    </PageShell>
  );
}


