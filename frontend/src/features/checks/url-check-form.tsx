"use client";

import { zodResolver } from "@hookform/resolvers/zod";
import { useMutation } from "@tanstack/react-query";
import { Link2, LoaderCircle } from "lucide-react";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { ApiErrorState } from "@/components/api-error";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { createIncident } from "@/features/incidents/api";

const schema = z.object({ url: z.string().trim().url("Enter a complete URL beginning with http:// or https://").max(2_048) });
type Values = z.infer<typeof schema>;

export function UrlCheckForm() {
  const router = useRouter();
  const form = useForm<Values>({ resolver: zodResolver(schema), defaultValues: { url: "" } });
  const mutation = useMutation({
    mutationFn: ({ url }: Values) => createIncident({ submission_type: "URL", text: url, title: "Suspicious URL" }),
    onSuccess: (incident) => router.push(`/incidents/${incident.id}`),
  });
  return (
    <Card>
      <CardHeader><CardTitle className="flex items-center gap-2"><Link2 className="size-5 text-emerald-800" /> Submit a suspicious URL</CardTitle><CardDescription>ADRIS parses the submitted address and its domain. It does not open, scrape, or guarantee the safety of the destination.</CardDescription></CardHeader>
      <CardContent>
        <form className="space-y-5" onSubmit={form.handleSubmit((values) => mutation.mutate(values))}>
          <div className="space-y-2"><Label htmlFor="url">Full URL</Label><Input id="url" type="url" inputMode="url" placeholder="https://example.invalid/verify" {...form.register("url")} /><p className="text-xs text-red-700">{form.formState.errors.url?.message}</p></div>
          {mutation.isError ? <ApiErrorState error={mutation.error} /> : null}
          <Button type="submit" size="lg" disabled={mutation.isPending}>{mutation.isPending ? <LoaderCircle className="animate-spin" /> : null}{mutation.isPending ? "Submitting…" : "Check this URL"}</Button>
        </form>
      </CardContent>
    </Card>
  );
}
