"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { Activity, Download, ListChecks, Map, Network, ScanSearch, ShieldCheck } from "lucide-react";
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

const links = [
  { href: "/analyst", label: "Overview", icon: Activity },
  { href: "/analyst/queue", label: "Queue", icon: ListChecks },
  { href: "/analyst/network", label: "Network", icon: Network },
  { href: "/analyst/map", label: "Map", icon: Map },
  { href: "/analyst/reviews", label: "Reviews", icon: ScanSearch },
  { href: "/analyst/exports", label: "Exports", icon: Download },
];

export function AnalystShell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="mx-auto max-w-[1500px] px-4 py-6 sm:px-6">
      <div className="mb-6 flex items-center gap-3"><span className="grid size-11 place-items-center rounded-2xl bg-slate-950 text-white"><ShieldCheck /></span><div><p className="text-xs font-bold uppercase tracking-[.18em] text-emerald-800">Protected workspace</p><h1 className="text-2xl font-black">ADRIS Analyst Console</h1></div></div>
      <nav className="mb-6 flex gap-2 overflow-x-auto rounded-2xl border bg-white p-2" aria-label="Analyst navigation">{links.map(({ href, label, icon: Icon }) => <Link key={href} href={href} className={cn("flex shrink-0 items-center gap-2 rounded-xl px-3 py-2 text-sm font-semibold", pathname === href ? "bg-emerald-800 text-white" : "text-slate-600 hover:bg-slate-100")}><Icon className="size-4" />{label}</Link>)}</nav>
      {children}
    </div>
  );
}
