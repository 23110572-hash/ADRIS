import type { Metadata } from "next";
import Link from "next/link";
import { Ban, KeyRound, LogOut, LucidePhoneCall, ShieldAlert, WalletCards } from "lucide-react";
import { PageShell } from "@/components/page-shell";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = { title: "Immediate digital-arrest help", description: "Reviewed safety instructions that do not depend on AI." };

const actions = [
  { icon: Ban, title: "There is no legal process called ‘digital arrest.’", detail: "Police, courts, CBI, ED, Customs, or regulators do not keep citizens under arrest over a video or phone call." },
  { icon: WalletCards, title: "Do not transfer money.", detail: "Do not make a safe-account, verification, tax, bail, penalty, or innocence-proving transfer." },
  { icon: KeyRound, title: "Do not disclose secrets or screen access.", detail: "Never share OTPs, PINs, passwords, CVVs, banking credentials, or install remote-control software." },
  { icon: LogOut, title: "End the interaction if it is safe.", detail: "Do not argue with the caller. Disconnect, move near a trusted person, and use another device if your screen is being shared." },
  { icon: LucidePhoneCall, title: "Contact a trusted channel now.", detail: "Call 1930, your bank using the number on its official website or card, or a trusted family member." },
];

export default function EmergencyPage() {
  return (
    <PageShell eyebrow="Works without AI" title="Stop. You are not under ‘digital arrest’." description="These reviewed instructions are designed to remain available from the installed ADRIS PWA even when analysis services are unavailable.">
      <div className="rounded-3xl border-2 border-red-300 bg-red-50 p-5 sm:p-8">
        <div className="mb-6 flex items-center gap-3 text-red-950"><span className="grid size-12 place-items-center rounded-2xl bg-red-700 text-white"><ShieldAlert className="size-7" /></span><div><strong className="block text-xl">Do not pay or share access</strong><span className="text-sm">Pause before doing anything the caller requested.</span></div></div>
        <ol className="space-y-3">{actions.map(({ icon: Icon, title, detail }, index) => <li key={title} className="flex gap-4 rounded-2xl border border-red-200 bg-white p-4"><span className="grid size-9 shrink-0 place-items-center rounded-full bg-red-100 font-black text-red-800">{index + 1}</span><div><h2 className="flex items-center gap-2 font-bold text-red-950"><Icon className="size-4" /> {title}</h2><p className="mt-1 text-sm leading-6 text-slate-700">{detail}</p></div></li>)}</ol>
        <div className="mt-6 flex flex-wrap gap-3"><Button asChild variant="destructive" size="lg"><a href="tel:1930"><LucidePhoneCall /> Call 1930</a></Button><Button asChild variant="outline" size="lg"><Link href="/check/message">Check submitted evidence</Link></Button><Button asChild variant="outline" size="lg"><Link href="/reporting">Reporting steps</Link></Button></div>
      </div>
      <p className="mt-5 text-sm leading-6 text-slate-600">If you are in immediate physical danger, contact local emergency services. ADRIS cannot listen to a live call, contact your bank, freeze an account, block a number, or file a police case for you.</p>
    </PageShell>
  );
}
