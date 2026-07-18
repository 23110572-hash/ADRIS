import Link from "next/link";
import { WifiOff } from "lucide-react";
import { PageShell } from "@/components/page-shell";
import { Button } from "@/components/ui/button";
export default function OfflinePage() {
  return <PageShell title="You are offline" description="Previously cached ADRIS safety guidance remains available, but new evidence cannot be submitted without a connection."><div className="rounded-2xl border bg-white p-8 text-center"><WifiOff className="mx-auto size-10 text-slate-500" /><p className="mt-4 font-bold">Do not transfer money or share OTPs, PINs, passwords, or screen access.</p><Button asChild variant="destructive" className="mt-5"><Link href="/emergency">Open cached emergency guidance</Link></Button></div></PageShell>;
}
