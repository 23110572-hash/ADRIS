import type { Metadata } from "next";
import { PageShell } from "@/components/page-shell";
import { CheckIntro } from "@/features/checks/check-intro";
import { UrlCheckForm } from "@/features/checks/url-check-form";

export const metadata: Metadata = { title: "Check a suspicious URL" };
export default function CheckUrlPage() {
  return <PageShell eyebrow="URL triage" title="Check a suspicious URL" description="Submit the complete address without opening it. ADRIS extracts the URL and domain but does not claim live reputation data unless an authorised source is configured."><CheckIntro>Do not sign in, enter payment details, or grant permissions on a suspicious page.</CheckIntro><UrlCheckForm /></PageShell>;
}
