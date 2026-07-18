import type { Metadata } from "next";
import { PageShell } from "@/components/page-shell";
import { CheckIntro } from "@/features/checks/check-intro";
import { UploadCheckForm } from "@/features/checks/upload-check-form";

export const metadata: Metadata = { title: "Check a screenshot or document" };
export default function CheckScreenshotPage() {
  return <PageShell eyebrow="Private evidence intake" title="Check a screenshot or document" description="Upload a screenshot, image, or PDF. The original is quarantined, validated, hashed, and kept separate from OCR derivatives."><CheckIntro>Crop unrelated conversations where possible, but never alter the relevant original if you may need it as evidence.</CheckIntro><UploadCheckForm submissionType="SCREENSHOT" title="Upload screenshot or document" description="Supported formats: JPEG, PNG, WebP, and PDF." accept="image/jpeg,image/png,image/webp,application/pdf" /></PageShell>;
}
