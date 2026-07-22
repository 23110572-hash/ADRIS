import Link from "next/link";
import { AlertTriangle } from "lucide-react";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";

export function ApiErrorState({ error, retry }: { error: unknown; retry?: () => void }) {
  const message = error instanceof Error ? error.message : "ADRIS could not reach the analysis service.";
  return (
    <Alert className="border-red-200 bg-red-50 text-red-950">
      <AlertTriangle className="mb-2 size-5" />
      <AlertTitle>Service unavailable</AlertTitle>
      <AlertDescription>{message} If this continues, open the emergency guidance for immediate safety steps.</AlertDescription>
      <div className="mt-4 flex flex-wrap gap-2">
        {retry ? <Button type="button" size="sm" variant="outline" onClick={retry}>Try again</Button> : null}
        <Button asChild size="sm" variant="destructive"><Link href="/emergency">Open emergency guidance</Link></Button>
      </div>
    </Alert>
  );
}
