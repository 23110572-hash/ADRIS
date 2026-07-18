import type { Metadata } from "next";
import { PageShell } from "@/components/page-shell";
import { CheckIntro } from "@/features/checks/check-intro";
import { UploadCheckForm } from "@/features/checks/upload-check-form";

export const metadata: Metadata = { title: "Check a QR code" };
export default function CheckQrPage() {
  return <PageShell eyebrow="QR payload inspection" title="Check a QR code" description="Upload or capture a clear QR image. ADRIS decodes the payload without asking you to approve a payment."><CheckIntro>Never scan an unknown QR inside a payment app just to discover where it leads.</CheckIntro><UploadCheckForm submissionType="QR" title="Upload or capture QR" description="Use a sharp, well-lit JPEG, PNG, or WebP image." accept="image/jpeg,image/png,image/webp" /></PageShell>;
}
