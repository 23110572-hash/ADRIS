import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function PageShell({
  eyebrow,
  title,
  description,
  children,
  className,
}: {
  eyebrow?: string;
  title: string;
  description?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("mx-auto w-full max-w-6xl px-4 py-10 sm:px-6 sm:py-14", className)}>
      <header className="mb-8 max-w-3xl">
        {eyebrow ? <p className="mb-2 text-sm font-bold uppercase tracking-[0.18em] text-emerald-800">{eyebrow}</p> : null}
        <h1 className="text-3xl font-black tracking-tight text-slate-950 sm:text-4xl">{title}</h1>
        {description ? <p className="mt-3 text-base leading-7 text-slate-600 sm:text-lg">{description}</p> : null}
      </header>
      {children}
    </div>
  );
}
