import type { Metadata } from "next";
import { PageShell } from "@/components/page-shell";
import { ResultView } from "@/features/incidents/result-view";

export const metadata: Metadata = { title: "Security Analysis Result" };
export default async function IncidentResultPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return (
    <PageShell
      eyebrow={`Submission Ref: #${id.slice(0, 8)}`}
      title="Security & Scam Risk Assessment"
      description="Detailed safety breakdown of your submitted text or evidence."
    >
      <ResultView incidentId={id} />
    </PageShell>
  );
}

