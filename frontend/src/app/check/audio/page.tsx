import type { Metadata } from "next";
import { PageShell } from "@/components/page-shell";
import { CheckIntro } from "@/features/checks/check-intro";
import { UploadCheckForm } from "@/features/checks/upload-check-form";

export const metadata: Metadata = { title: "Check consented audio" };
export default function CheckAudioPage() {
  return <PageShell eyebrow="Consented audio" title="Check an audio recording" description="Upload an existing recording or record through your browser with consent. ADRIS does not intercept or listen to live calls."><CheckIntro>Only submit audio you are legally permitted to record and share. Recording laws and consent requirements may vary.</CheckIntro><UploadCheckForm submissionType="AUDIO" title="Upload or record audio" description="Supported browser uploads include MP3, WAV, OGG, WebM, and MP4 audio up to 25 MB." accept="audio/mpeg,audio/wav,audio/x-wav,audio/ogg,audio/webm,audio/mp4,video/webm" allowRecording /></PageShell>;
}
