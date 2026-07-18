"use client";

import { useMutation } from "@tanstack/react-query";
import { FileUp, LoaderCircle, Mic, Square } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ApiErrorState } from "@/components/api-error";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { uploadIncidentFile, type SubmissionType } from "@/features/incidents/api";

const MAX_BYTES = 25 * 1024 * 1024;

function normalizedFile(file: File): File {
  if (file.type) return file;
  const extension = file.name.split(".").pop()?.toLowerCase();
  const type = extension === "pdf" ? "application/pdf" : extension === "png" ? "image/png" : extension === "jpg" || extension === "jpeg" ? "image/jpeg" : extension === "wav" ? "audio/wav" : extension === "mp3" ? "audio/mpeg" : "application/octet-stream";
  return new File([file], file.name, { type, lastModified: file.lastModified });
}

export function UploadCheckForm({
  submissionType,
  title,
  description,
  accept,
  allowRecording = false,
}: {
  submissionType: Exclude<SubmissionType, "MESSAGE" | "URL">;
  title: string;
  description: string;
  accept: string;
  allowRecording?: boolean;
}) {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [consent, setConsent] = useState(!allowRecording);
  const [recording, setRecording] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const chunks = useRef<Blob[]>([]);

  useEffect(() => () => stream.current?.getTracks().forEach((track) => track.stop()), []);

  const mutation = useMutation({
    mutationFn: (selected: File) => uploadIncidentFile({ submissionType, file: normalizedFile(selected), consentConfirmed: consent }),
    onSuccess: (incident) => router.push(`/incidents/${incident.id}`),
  });

  async function startRecording() {
    setLocalError(null);
    if (!consent) return setLocalError("Confirm that you have the right and consent to submit this recording.");
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") return setLocalError("Audio recording is not supported in this browser. Upload an existing recording instead.");
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({ audio: true });
      chunks.current = [];
      const nextRecorder = new MediaRecorder(stream.current, { mimeType: MediaRecorder.isTypeSupported("audio/webm") ? "audio/webm" : "" });
      nextRecorder.ondataavailable = (event) => { if (event.data.size) chunks.current.push(event.data); };
      nextRecorder.onstop = () => {
        const blob = new Blob(chunks.current, { type: nextRecorder.mimeType || "audio/webm" });
        setFile(new File([blob], `consented-recording-${Date.now()}.webm`, { type: blob.type }));
        stream.current?.getTracks().forEach((track) => track.stop());
        setRecording(false);
      };
      recorder.current = nextRecorder;
      nextRecorder.start(500);
      setRecording(true);
    } catch (error) {
      setLocalError(error instanceof Error ? error.message : "Microphone access was not granted.");
    }
  }

  function selectFile(selected: File | null) {
    setLocalError(null);
    if (selected && selected.size > MAX_BYTES) return setLocalError("The maximum file size is 25 MB.");
    setFile(selected);
  }

  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2"><FileUp className="size-5 text-emerald-800" /> {title}</CardTitle><CardDescription>{description}</CardDescription></CardHeader>
      <CardContent className="space-y-5">
        {allowRecording ? (
          <label className="flex items-start gap-3 rounded-xl border bg-slate-50 p-4 text-sm leading-6">
            <input type="checkbox" checked={consent} onChange={(event) => setConsent(event.target.checked)} className="mt-1 size-4 accent-emerald-800" />
            <span><strong className="block">I confirm consent and lawful possession</strong>I have the right to record or upload this audio. ADRIS does not listen to live calls.</span>
          </label>
        ) : null}
        <div className="space-y-2"><Label htmlFor={`file-${submissionType}`}>Choose file</Label><Input id={`file-${submissionType}`} type="file" accept={accept} capture={submissionType === "QR" ? "environment" : undefined} onChange={(event) => selectFile(event.target.files?.[0] ?? null)} /></div>
        {allowRecording ? (
          <div className="flex flex-wrap items-center gap-3">
            {!recording ? <Button type="button" variant="outline" onClick={startRecording}><Mic /> Record audio</Button> : <Button type="button" variant="destructive" onClick={() => recorder.current?.stop()}><Square /> Stop recording</Button>}
            <span className="text-sm text-slate-600">{recording ? "Recording locally in your browser…" : "Recording is uploaded only after you submit."}</span>
          </div>
        ) : null}
        {file ? <Alert className="border-emerald-200 bg-emerald-50 text-emerald-950"><AlertTitle>Ready to upload</AlertTitle><AlertDescription>{file.name} · {(file.size / 1024 / 1024).toFixed(2)} MB · {file.type || "type not reported"}</AlertDescription></Alert> : null}
        {localError ? <Alert className="border-red-200 bg-red-50 text-red-950"><AlertTitle>Cannot use this file</AlertTitle><AlertDescription>{localError}</AlertDescription></Alert> : null}
        {mutation.isError ? <ApiErrorState error={mutation.error} /> : null}
        <Button type="button" size="lg" disabled={!file || mutation.isPending || (allowRecording && !consent)} onClick={() => file && mutation.mutate(file)}>
          {mutation.isPending ? <LoaderCircle className="animate-spin" /> : <FileUp />}{mutation.isPending ? "Encrypting and uploading…" : "Upload privately and analyze"}
        </Button>
        <p className="text-xs leading-5 text-slate-500">Maximum 25 MB. The browser uploads directly to a private S3 quarantine location using a short-lived URL; ADRIS never creates a public object URL.</p>
      </CardContent>
    </Card>
  );
}
