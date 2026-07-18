import type { Metadata } from "next";
import { PageShell } from "@/components/page-shell";
import { CheckIntro } from "@/features/checks/check-intro";
import { MessageCheckForm } from "@/features/checks/message-check-form";

export const metadata: Metadata = { title: "Check a suspicious message" };
export default function CheckMessagePage() {
  return <PageShell eyebrow="Citizen fraud shield" title="Check a message or transcript" description="Submit text you received or a transcript you created. Deterministic extraction runs before bounded AI analysis."><CheckIntro>Text is stored with the incident for analysis and evidence preservation. Remove unrelated personal details.</CheckIntro><MessageCheckForm /></PageShell>;
}
