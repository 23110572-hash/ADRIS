"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  AlertOctagon,
  CheckCircle2,
  ChevronDown,
  CircleHelp,
  FileLock2,
  Info,
  ShieldAlert,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { ApiErrorState } from "@/components/api-error";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ExportControl } from "@/features/incidents/export-control";
import { getAssessment, preserveIncident } from "@/features/incidents/api";
import type { RiskBand } from "@/types/api";

const PRESENTATION: Record<
  RiskBand,
  {
    title: string;
    badgeText: string;
    icon: typeof AlertOctagon;
    className: string;
    badgeVariant: "danger" | "warning" | "success" | "outline";
    subtitle: string;
  }
> = {
  HIGH_RISK: {
    title: "High Scam Risk Detected",
    badgeText: "HIGH RISK",
    icon: AlertOctagon,
    className: "border-red-300 bg-red-50 text-red-950",
    badgeVariant: "danger",
    subtitle: "Multiple strong scam indicators were identified. Do not respond or send money.",
  },
  CAUTION: {
    title: "Suspicious Elements Found – Exercise Caution",
    badgeText: "EXERCISE CAUTION",
    icon: TriangleAlert,
    className: "border-amber-300 bg-amber-50 text-amber-950",
    badgeVariant: "warning",
    subtitle: "Suspicious patterns or incomplete information detected. Verify independently before proceeding.",
  },
  NO_STRONG_SIGNAL: {
    title: "No Obvious Scam Signals Detected",
    badgeText: "LOW RISK DETECTED",
    icon: CheckCircle2,
    className: "border-emerald-300 bg-emerald-50 text-emerald-950",
    badgeVariant: "success",
    subtitle: "No known high-risk scam patterns were identified in the text or files provided.",
  },
  UNABLE_TO_ASSESS: {
    title: "Unable to Assess Submission Reliably",
    badgeText: "INSUFFICIENT DATA",
    icon: CircleHelp,
    className: "border-slate-300 bg-slate-50 text-slate-950",
    badgeVariant: "outline",
    subtitle: "The submission could not be evaluated reliably. Please treat unresolved requests cautiously.",
  },
};

const REASON_LABELS: Record<string, string> = {
  NO_STRONG_SIGNAL_DETECTED: "No known scam links, urgent payment demands, or imposter phone numbers were detected.",
  AUTHORIZED_HIGH_SEVERITY_MATCH: "Matched known high-risk fraudulent accounts or malicious links.",
  BANK_IMPERSONATION_URGENCY: "Contains urgent demands pretending to be your bank or financial institution.",
  AGENT_DISAGREEMENT: "Analysis flagged mixed indicators that suggest caution.",
  INCOMPLETE_EVIDENCE: "The submitted message or document was incomplete.",
  INPUT_QUALITY_INSUFFICIENT: "The submitted text or image was too short or unclear to evaluate.",
  INSUFFICIENT_COVERAGE: "Insufficient evidence was provided for a complete risk evaluation.",
};

const MISSING_SOURCE_LABELS: Record<string, string> = {
  COARSE_LOCATION_NOT_PROVIDED: "Location details were not attached (Optional)",
  AUDIO_TRANSCRIPTION_UNAVAILABLE: "Audio recording was not provided",
  OCR_TEXT_UNAVAILABLE: "Image text extraction was unavailable",
};

export function ResultView({ incidentId }: { incidentId: string }) {
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);
  const query = useQuery({ queryKey: ["assessment", incidentId], queryFn: () => getAssessment(incidentId) });
  const preserve = useMutation({ mutationFn: () => preserveIncident(incidentId) });

  if (query.isPending) {
    return (
      <Card>
        <CardContent className="p-8 text-sm text-slate-600">
          Evaluating safety and risk assessment...
        </CardContent>
      </Card>
    );
  }

  if (query.isError) return <ApiErrorState error={query.error} retry={() => query.refetch()} />;

  const assessment = query.data;
  const view = PRESENTATION[assessment.risk_band] || PRESENTATION.UNABLE_TO_ASSESS;
  const Icon = view.icon;

  return (
    <div className="space-y-6">
      {/* Primary Risk Assessment Banner */}
      <section className={`rounded-3xl border p-6 sm:p-8 ${view.className}`}>
        <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="flex items-center gap-3">
              <Icon className="size-10 shrink-0" />
              <h2 className="text-2xl font-black sm:text-3xl">{view.title}</h2>
            </div>
            <p className="mt-3 max-w-3xl text-base leading-7">{assessment.explanation || view.subtitle}</p>
          </div>
          <Badge variant={view.badgeVariant} className="w-fit text-sm font-semibold tracking-wide">
            {view.badgeText}
          </Badge>
        </div>

        {assessment.risk_band === "NO_STRONG_SIGNAL" && (
          <div className="mt-5 flex gap-3 rounded-2xl border border-emerald-300/80 bg-white/80 p-4 text-sm font-medium text-emerald-950">
            <Info className="mt-0.5 size-5 shrink-0 text-emerald-700" />
            <p>
              <strong>Important Note:</strong> While no scam indicators were found, this result does not guarantee that an unknown person, payment link, or unexpected message is 100% safe. Always verify payments through official numbers.
            </p>
          </div>
        )}
      </section>

      {/* Analysis Details & Immediate Guidance */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Why ADRIS returned this result */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldAlert className="size-5 text-emerald-700" /> Why you received this result
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <ul className="space-y-3">
              {assessment.reason_codes.map((reason) => {
                const label = REASON_LABELS[reason] || reason.replaceAll("_", " ").toLowerCase();
                return (
                  <li key={reason} className="flex gap-3 rounded-xl bg-slate-50 p-3.5 text-sm leading-6 text-slate-800">
                    <ShieldCheck className="mt-0.5 size-4 shrink-0 text-emerald-700" />
                    <span>{label}</span>
                  </li>
                );
              })}
            </ul>
          </CardContent>
        </Card>

        {/* What to do now */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <ShieldCheck className="size-5 text-emerald-700" /> Recommended safety steps
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="space-y-3">
              {assessment.safety_actions.map((action, index) => (
                <li key={action} className="flex gap-3 text-sm leading-6 text-slate-800">
                  <span className="grid size-7 shrink-0 place-items-center rounded-full bg-emerald-800 text-xs font-bold text-white">
                    {index + 1}
                  </span>
                  <span>{action}</span>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      </div>

      {/* Missing Information / Optional Data */}
      {assessment.missing_sources.length > 0 && (
        <Card className="border-slate-200 bg-slate-50/50">
          <CardHeader className="pb-3">
            <CardTitle className="text-base text-slate-800">Additional Context & Unchecked Data</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc space-y-1 pl-5 text-sm text-slate-600">
              {assessment.missing_sources.map((source) => (
                <li key={source}>
                  {MISSING_SOURCE_LABELS[source] || source.replaceAll("_", " ")}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Preserve and Report Evidence */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileLock2 className="size-5" /> Preserve evidence & report incident
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <p className="text-sm text-slate-600 leading-6">
            If you believe you are a victim of cyber fraud, keep the original message and generate a sealed evidence package for law enforcement or your bank.
          </p>
          <div className="flex flex-wrap gap-3">
            <Button onClick={() => preserve.mutate()} disabled={preserve.isPending || preserve.isSuccess}>
              {preserve.isSuccess ? "Evidence preserved" : preserve.isPending ? "Sealing manifest…" : "Preserve evidence"}
            </Button>
            <ExportControl incidentId={incidentId} />
            <Button asChild variant="outline">
              <Link href={`/incidents/${incidentId}/evidence`}>Review evidence</Link>
            </Button>
            <Button asChild variant="destructive">
              <Link href="/reporting">Reporting guidance</Link>
            </Button>
          </div>
        </CardContent>
        {preserve.isError && (
          <CardContent>
            <ApiErrorState error={preserve.error} />
          </CardContent>
        )}
      </Card>

      {/* Collapsible Technical Audit Details */}
      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-4">
        <button
          type="button"
          onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
          className="flex w-full items-center justify-between text-xs font-semibold text-slate-600 hover:text-slate-900"
        >
          <span>Technical Audit & System Information</span>
          <ChevronDown className={`size-4 transition-transform ${showTechnicalDetails ? "rotate-180" : ""}`} />
        </button>

        {showTechnicalDetails && (
          <div className="mt-4 space-y-2 border-t border-slate-200 pt-3 text-xs text-slate-600">
            <div className="flex flex-wrap gap-2">
              <Badge variant="outline">Policy: {assessment.policy_version}</Badge>
              <Badge variant="outline">Input Quality: {assessment.input_quality}</Badge>
              {assessment.agent_disagreement && <Badge variant="warning">Agent Disagreement Flagged</Badge>}
            </div>
            <p className="pt-2 text-[11px] text-slate-500">
              ADRIS policy engine v1.0.0. The final risk band is determined deterministically by system policy based on bounded LLM agent outputs.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

