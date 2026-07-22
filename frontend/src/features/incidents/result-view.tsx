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
    title: "High Risk Scam Detected",
    badgeText: "HIGH RISK",
    icon: AlertOctagon,
    className: "border-red-300 bg-red-50 text-red-950",
    badgeVariant: "danger",
    subtitle: "We found strong signs of a scam. Please do not send money, click links, or reply to this message.",
  },
  CAUTION: {
    title: "Suspicious Request Please Be Careful",
    badgeText: "BE CAREFUL",
    icon: TriangleAlert,
    className: "border-amber-300 bg-amber-50 text-amber-950",
    badgeVariant: "warning",
    subtitle: "We found suspicious signs in your submission. Please double check with official bank contacts before taking any action.",
  },
  NO_STRONG_SIGNAL: {
    title: "No Scam Warnings Found",
    badgeText: "LOOKS SAFE",
    icon: CheckCircle2,
    className: "border-emerald-300 bg-emerald-50 text-emerald-950",
    badgeVariant: "success",
    subtitle: "Our check did not find any known scam links, fake demands, or suspicious patterns in what you submitted.",
  },
  UNABLE_TO_ASSESS: {
    title: "Need More Information",
    badgeText: "UNSURE",
    icon: CircleHelp,
    className: "border-slate-300 bg-slate-50 text-slate-950",
    badgeVariant: "outline",
    subtitle: "We could not find enough clear text or evidence to complete a safety check. Please stay careful with unknown requests.",
  },
};

const REASON_LABELS: Record<string, string> = {
  NO_STRONG_SIGNAL_DETECTED: "Our check did not find any fake links, urgent money demands, or known scam phone numbers.",
  AUTHORIZED_HIGH_SEVERITY_MATCH: "Matches known fake account numbers or dangerous fraudulent links.",
  BANK_IMPERSONATION_URGENCY: "Contains urgent messages pretending to be your bank or official service.",
  AGENT_DISAGREEMENT: "Mixed indicators found so extra care is recommended.",
  INCOMPLETE_EVIDENCE: "The submitted message or document was incomplete.",
  INPUT_QUALITY_INSUFFICIENT: "The submitted text or photo was too blurry or short to read.",
  INSUFFICIENT_COVERAGE: "Not enough information was available to run a full safety check.",
};

const MISSING_SOURCE_LABELS: Record<string, string> = {
  COARSE_LOCATION_NOT_PROVIDED: "Location details were not included",
  AUDIO_TRANSCRIPTION_UNAVAILABLE: "Audio recording was not provided",
  OCR_TEXT_UNAVAILABLE: "Text from images could not be read",
};

export function ResultView({ incidentId }: { incidentId: string }) {
  const [showTechnicalDetails, setShowTechnicalDetails] = useState(false);
  const query = useQuery({ queryKey: ["assessment", incidentId], queryFn: () => getAssessment(incidentId) });
  const preserve = useMutation({ mutationFn: () => preserveIncident(incidentId) });

  if (query.isPending) {
    return (
      <Card>
        <CardContent className="p-8 text-base text-slate-700">
          Checking your submission for scam signs...
        </CardContent>
      </Card>
    );
  }

  if (query.isError) return <ApiErrorState error={query.error} retry={() => query.refetch()} />;

  const assessment = query.data;
  const view = PRESENTATION[assessment.risk_band] || PRESENTATION.UNABLE_TO_ASSESS;
  const Icon = view.icon;

  return (
    <div className="space-y-8">
      {/* Primary Risk Assessment Banner */}
      <section className={`rounded-3xl border p-6 sm:p-8 ${view.className}`}>
        <div className="flex flex-col gap-5 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="flex items-center gap-3">
              <Icon className="size-10 shrink-0" />
              <h2 className="text-3xl font-black sm:text-4xl">{view.title}</h2>
            </div>
            <p className="mt-4 max-w-3xl text-lg leading-relaxed text-slate-900">{assessment.explanation || view.subtitle}</p>
          </div>
          <Badge variant={view.badgeVariant} className="w-fit text-base font-bold tracking-wide py-1.5 px-4 rounded-xl">
            {view.badgeText}
          </Badge>
        </div>

        {assessment.risk_band === "NO_STRONG_SIGNAL" && (
          <div className="mt-6 flex gap-3.5 rounded-2xl border border-emerald-300 bg-white/90 p-5 text-base font-medium text-emerald-950">
            <Info className="mt-0.5 size-6 shrink-0 text-emerald-700" />
            <p className="leading-relaxed">
              <strong>Important Advice:</strong> Even if no scam signs were found, never transfer money, share OTPs, or give passwords to anyone over phone or text. Always verify unknown requests directly with your bank.
            </p>
          </div>
        )}
      </section>

      {/* Analysis Details & Immediate Guidance */}
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Why you received this result */}
        <Card className="border-slate-200 shadow-sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2.5 text-xl font-bold">
              <ShieldAlert className="size-6 text-emerald-700" /> Why you received this result
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <ul className="space-y-3.5">
              {assessment.reason_codes.map((reason) => {
                const cleanReasonKey = reason.replaceAll("-", "_");
                const label = REASON_LABELS[cleanReasonKey] || cleanReasonKey.replaceAll("_", " ").toLowerCase();
                return (
                  <li key={reason} className="flex gap-3.5 rounded-2xl bg-slate-50 p-4 text-base leading-relaxed text-slate-800 border border-slate-100">
                    <ShieldCheck className="mt-0.5 size-5 shrink-0 text-emerald-700" />
                    <span>{label}</span>
                  </li>
                );
              })}
            </ul>
          </CardContent>
        </Card>

        {/* What to do now */}
        <Card className="border-slate-200 shadow-sm">
          <CardHeader>
            <CardTitle className="flex items-center gap-2.5 text-xl font-bold">
              <ShieldCheck className="size-6 text-emerald-700" /> Recommended safety steps
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="space-y-4">
              {assessment.safety_actions.map((action, index) => (
                <li key={action} className="flex gap-3.5 text-base leading-relaxed text-slate-800">
                  <span className="grid size-8 shrink-0 place-items-center rounded-full bg-emerald-800 text-sm font-bold text-white">
                    {index + 1}
                  </span>
                  <span className="mt-0.5">{action}</span>
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      </div>

      {/* Missing Information / Optional Data */}
      {assessment.missing_sources.length > 0 && (
        <Card className="border-slate-200 bg-slate-50/80 shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-lg font-bold text-slate-800">Information not provided</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc space-y-2 pl-6 text-base text-slate-700">
              {assessment.missing_sources.map((source) => {
                const cleanSourceKey = source.replaceAll("-", "_");
                return (
                  <li key={source}>
                    {MISSING_SOURCE_LABELS[cleanSourceKey] || cleanSourceKey.replaceAll("_", " ")}
                  </li>
                );
              })}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Preserve and Report Evidence */}
      <Card className="border-slate-200 shadow-sm">
        <CardHeader>
          <CardTitle className="flex items-center gap-2.5 text-xl font-bold">
            <FileLock2 className="size-6 text-slate-800" /> Save Evidence and Report
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-5">
          <p className="text-base text-slate-700 leading-relaxed">
            If you lost money or believe someone is trying to scam you, save the evidence record below to share with your bank or local police.
          </p>
          <div className="flex flex-wrap gap-3.5">
            <Button size="lg" className="text-base font-semibold" onClick={() => preserve.mutate()} disabled={preserve.isPending || preserve.isSuccess}>
              {preserve.isSuccess ? "Evidence Saved" : preserve.isPending ? "Saving Record..." : "Save Official Evidence"}
            </Button>
            <ExportControl incidentId={incidentId} />
            <Button size="lg" asChild variant="outline" className="text-base font-semibold">
              <Link href={`/incidents/${incidentId}/evidence`}>View Submitted Evidence</Link>
            </Button>
            <Button size="lg" asChild variant="destructive" className="text-base font-semibold">
              <Link href="/reporting">Cyber Fraud Helpline</Link>
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
      <div className="rounded-2xl border border-slate-200 bg-slate-50 p-5">
        <button
          type="button"
          onClick={() => setShowTechnicalDetails(!showTechnicalDetails)}
          className="flex w-full items-center justify-between text-base font-semibold text-slate-700 hover:text-slate-900"
        >
          <span>System Technical Details</span>
          <ChevronDown className={`size-5 transition-transform ${showTechnicalDetails ? "rotate-180" : ""}`} />
        </button>

        {showTechnicalDetails && (
          <div className="mt-4 space-y-3 border-t border-slate-200 pt-4 text-sm text-slate-700">
            <div className="flex flex-wrap gap-2.5">
              <Badge variant="outline" className="text-sm py-1 px-3">Policy Version 1.0</Badge>
              <Badge variant="outline" className="text-sm py-1 px-3">Quality {assessment.input_quality}</Badge>
              {assessment.agent_disagreement && <Badge variant="warning" className="text-sm py-1 px-3">Review Flagged</Badge>}
            </div>
            <p className="pt-1 text-sm text-slate-600 leading-relaxed">
              Official safety evaluation record generated by ADRIS automated risk engine.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}


