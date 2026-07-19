import Link from "next/link";
import { AdrisLogo } from "@/components/adris-logo";

export function SiteFooter() {
  return (
    <footer className="mt-auto border-t bg-white">
      <div className="mx-auto grid max-w-7xl gap-8 px-4 py-10 text-sm sm:px-6 md:grid-cols-[1fr_auto]">
        <div className="max-w-2xl">
          <div className="flex items-center"><AdrisLogo size="xl" /></div>
          <p className="mt-3 leading-6 text-slate-600">Decision support for digital-fraud safety and evidence preservation. ADRIS does not replace police, banks, courts, lawyers, or emergency services and does not declare anyone guilty.</p>
        </div>
        <nav className="grid grid-cols-2 gap-x-7 gap-y-3 font-semibold text-slate-700" aria-label="Footer navigation">
          <Link href="/emergency">Emergency help</Link>
          <Link href="/check/message">Check message</Link>
          <Link href="/check/screenshot">Upload evidence</Link>
          <Link href="/reporting">Official reporting</Link>
          <Link href="/analyst">Analyst console</Link>
        </nav>
      </div>
    </footer>
  );
}
