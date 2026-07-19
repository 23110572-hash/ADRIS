import Link from "next/link";
import { ArrowRight, FileSearch, Headphones, Link2, MessageSquareText, QrCode, ShieldAlert } from "lucide-react";

const checks = [
  { href: "/check/message", label: "Message or transcript", icon: MessageSquareText },
  { href: "/check/screenshot", label: "Screenshot or document", icon: FileSearch },
  { href: "/check/url", label: "Suspicious URL", icon: Link2 },
  { href: "/check/qr", label: "QR code", icon: QrCode },
  { href: "/check/audio", label: "Consented audio", icon: Headphones },
];

export default function HomePage() {
  return (
    <div className="safe-grid">
      <section className="mx-auto grid max-w-7xl gap-10 px-4 py-14 sm:px-6 lg:grid-cols-[1.25fr_.75fr] lg:py-24">
        <div>
          <p className="mb-4 inline-flex rounded-full border border-emerald-200 bg-emerald-50 px-3 py-1 text-sm font-semibold text-emerald-900">Citizen-first fraud safety</p>
          <h1 className="max-w-3xl text-5xl font-black tracking-tight text-slate-950 sm:text-7xl leading-tight">Verify Suspicious Requests & Stay Safe from Fraud.</h1>
          <p className="mt-6 max-w-2xl text-xl leading-9 text-slate-700">ADRIS checks submitted messages and evidence for coercion, government impersonation, fake “digital arrest” claims, and payment pressure. It preserves what you provide and explains its limits.</p>
          <div className="mt-8 flex flex-wrap gap-4">
            <Link href="/check/message" className="inline-flex items-center gap-2 rounded-xl bg-emerald-800 px-6 py-4 text-lg font-semibold text-white hover:bg-emerald-900">Check suspicious content <ArrowRight className="size-5" /></Link>
            <Link href="/emergency" className="inline-flex items-center gap-2 rounded-xl border border-red-300 bg-white px-6 py-4 text-lg font-semibold text-red-800 hover:bg-red-50"><ShieldAlert className="size-5" /> Get urgent guidance</Link>
          </div>
        </div>
        <aside className="rounded-3xl border bg-white p-8 shadow-xl shadow-emerald-950/5">
          <h2 className="text-xl font-black text-slate-950">What would you like to check?</h2>
          <div className="mt-6 grid gap-3">
            {checks.map(({ href, label, icon: Icon }) => (
              <Link key={href} href={href} className="flex items-center justify-between rounded-xl border p-5 hover:border-emerald-500 hover:bg-emerald-50 text-base font-semibold transition-all">
                <span className="flex items-center gap-3"><Icon className="size-6 text-emerald-800" /> {label}</span><ArrowRight className="size-4 text-slate-400" />
              </Link>
            ))}
          </div>
        </aside>
      </section>
      <section className="border-y bg-white/90">
        <div className="mx-auto grid max-w-7xl gap-8 px-4 py-12 sm:grid-cols-3 sm:px-6">
          <div><strong className="block text-lg font-bold text-emerald-900">No automated accusation</strong><span className="mt-1 block text-sm leading-6 text-slate-600">Signals inform a deterministic policy and human review.</span></div>
          <div><strong className="block text-lg font-bold text-emerald-900">Evidence-first</strong><span className="mt-1 block text-sm leading-6 text-slate-600">Private originals, hashes, lineage, and controlled downloads.</span></div>
          <div><strong className="block text-lg font-bold text-emerald-900">Honest limitations</strong><span className="mt-1 block text-sm leading-6 text-slate-600">No access to calls, banks, WhatsApp, or government systems.</span></div>
        </div>
      </section>
    </div>
  );
}
