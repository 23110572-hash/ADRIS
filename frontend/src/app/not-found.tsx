import Link from "next/link";
import { SearchX } from "lucide-react";
import { PageShell } from "@/components/page-shell";
import { Button } from "@/components/ui/button";
export default function NotFound() {
  return <PageShell title="Page not found" description="The requested ADRIS route does not exist or the incident is not accessible."><div className="rounded-2xl border bg-white p-8 text-center"><SearchX className="mx-auto size-10 text-slate-400" /><Button asChild className="mt-5"><Link href="/">Return home</Link></Button></div></PageShell>;
}
