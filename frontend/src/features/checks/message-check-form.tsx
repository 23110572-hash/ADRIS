"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { LoaderCircle, MessageSquareText } from "lucide-react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { ApiErrorState } from "@/components/api-error";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { createIncident } from "@/features/incidents/api";

const schema = z.object({
  message: z.string().trim().min(10, "Paste at least 10 characters so ADRIS has enough context.").max(50_000, "Message is too long."),
});
type Values = z.infer<typeof schema>;

export function MessageCheckForm() {
  const router = useRouter();
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { message: "" } });
  const mutation = useMutation({
    mutationFn: ({ message }: Values) => createIncident({ submission_type: "MESSAGE", text: message, language: "en-IN" }),
    onSuccess: (incident) => router.push(`/incidents/${incident.id}`),
  });

  return (
    <Card className="overflow-hidden">
      <CardHeader className="border-b bg-slate-50/70">
        <CardTitle className="flex items-center gap-2"><MessageSquareText className="size-5 text-emerald-800" /> Paste suspicious text</CardTitle>
        <CardDescription>Include the claimed authority, threats, payment instructions, and secrecy requests. Remove unrelated personal conversation.</CardDescription>
      </CardHeader>
      <CardContent className="pt-6">
        <form className="space-y-5" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
          <div className="space-y-2">
            <Label htmlFor="message">Message or transcript</Label>
            <Textarea id="message" placeholder="Example: I am calling from... transfer the verification amount now..." {...form.register("message")} />
            <div className="flex justify-between gap-3 text-xs text-slate-500">
              <span>{form.formState.errors.message?.message ?? "Do not include OTPs, passwords, PINs, or CVVs."}</span>
              <span>{form.watch("message").length.toLocaleString()} / 50,000</span>
            </div>
          </div>
          {mutation.isError ? <ApiErrorState error={mutation.error} /> : null}
          <Button type="submit" size="lg" disabled={mutation.isPending}>
            {mutation.isPending ? <LoaderCircle className="animate-spin" /> : null}
            {mutation.isPending ? "Creating secure incident…" : "Check this message"}
          </Button>
        </form>
      </CardContent>
    </Card>
  );
}
