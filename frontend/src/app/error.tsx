"use client";

import { useEffect } from "react";
import { PageShell } from "@/components/page-shell";
import { ApiErrorState } from "@/components/api-error";

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => { console.error("ADRIS UI error", error.digest ?? error.name); }, [error]);
  return <PageShell title="ADRIS could not display this page" description="No evidence was changed by this display error."><ApiErrorState error={error} retry={reset} /></PageShell>;
}
