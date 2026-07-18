import type { Metadata } from "next";
import { ArrowUpRight, Building2, Landmark, PhoneCall, RadioTower } from "lucide-react";
import { PageShell } from "@/components/page-shell";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export const metadata: Metadata = { title: "Official reporting guidance" };
const channels = [
  { icon: PhoneCall, title: "1930 cyber-fraud helpline", detail: "If money was transferred or credentials were exposed, call promptly. Keep transaction IDs, recipient details, timestamps, and your bank complaint number ready.", href: "tel:1930", action: "Call 1930" },
  { icon: Landmark, title: "National Cyber Crime Reporting Portal", detail: "Use the official portal to submit a cybercrime complaint. ADRIS does not submit it automatically or claim portal integration.", href: "https://cybercrime.gov.in/", action: "Open cybercrime.gov.in" },
  { icon: RadioTower, title: "Chakshu on Sanchar Saathi", detail: "Use Chakshu for suspected fraudulent communications such as calls, SMS, or messaging requests where applicable.", href: "https://sancharsaathi.gov.in/sfc/", action: "Open Chakshu" },
  { icon: Building2, title: "Your bank’s official fraud channel", detail: "Call the number printed on your card or listed on the bank’s official website. Do not use a number supplied by the suspicious caller.", href: null, action: null },
];
export default function ReportingPage() {
  return <PageShell eyebrow="Manual official handoff" title="Report through official channels" description="ADRIS prepares information and evidence. It does not file police cases, freeze accounts, block numbers, or submit to government portals.">
    <Alert className="mb-6 border-red-200 bg-red-50 text-red-950"><AlertTitle>Money transferred?</AlertTitle><AlertDescription>Contact 1930 and your bank immediately. Speed can matter, but only the authorised institution can attempt a hold or recovery.</AlertDescription></Alert>
    <div className="grid gap-4 sm:grid-cols-2">{channels.map(({ icon: Icon, title, detail, href, action }) => <Card key={title}><CardHeader><CardTitle className="flex items-center gap-2"><Icon className="size-5 text-emerald-800" /> {title}</CardTitle></CardHeader><CardContent><p className="text-sm leading-6 text-slate-600">{detail}</p>{href && action ? <Button asChild variant="outline" className="mt-4"><a href={href} target={href.startsWith("http") ? "_blank" : undefined} rel={href.startsWith("http") ? "noreferrer" : undefined}>{action}<ArrowUpRight /></a></Button> : null}</CardContent></Card>)}</div>
    <Card className="mt-6"><CardHeader><CardTitle>Prepare before reporting</CardTitle></CardHeader><CardContent><ul className="grid gap-2 text-sm leading-6 sm:grid-cols-2"><li>• Original messages, screenshots, or recordings</li><li>• Phone numbers, URLs, UPI IDs, and QR payloads</li><li>• Transaction reference, amount, and timestamp</li><li>• Bank complaint number and contact time</li><li>• A concise chronology in your own words</li><li>• ADRIS package, clearly labelled as decision support</li></ul></CardContent></Card>
  </PageShell>;
}
