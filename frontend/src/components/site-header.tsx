"use client";

import { SignInButton, UserButton, useAuth } from "@clerk/nextjs";
import { Menu } from "lucide-react";
import Image from "next/image";
import Link from "next/link";
import { Button } from "@/components/ui/button";

const navigation = [
  { href: "/check/message", label: "Check evidence" },
  { href: "/reporting", label: "Report safely" },
  { href: "/analyst", label: "Analyst" },
];

function ClerkControls() {
  const { isLoaded, isSignedIn } = useAuth();

  if (!isLoaded) return <span className="h-8 w-16 animate-pulse rounded-lg bg-slate-100" aria-label="Loading account" />;
  if (isSignedIn) return <UserButton />;

  return (
    <SignInButton mode="modal">
      <Button variant="ghost" size="sm">Sign in</Button>
    </SignInButton>
  );
}

export function SiteHeader() {
  const clerkConfigured = Boolean(process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY);
  return (
    <header className="sticky top-0 z-50 border-b bg-white/95 backdrop-blur supports-[backdrop-filter]:bg-white/85">
      <div className="mx-auto flex min-h-16 max-w-7xl items-center justify-between gap-3 px-4 sm:px-6">
        <Link href="/" className="flex items-center" aria-label="ADRIS home">
          <Image src="/logo.png" alt="ADRIS Logo" width={260} height={130} priority className="h-20 w-auto object-contain" />
        </Link>
        <nav className="hidden items-center gap-5 text-sm font-semibold md:flex" aria-label="Primary navigation">
          {navigation.map((item) => <Link key={item.href} href={item.href} className="text-slate-700 transition-colors hover:text-emerald-800">{item.label}</Link>)}
        </nav>
        <div className="flex items-center gap-2">
          {clerkConfigured ? <ClerkControls /> : null}
          <Button asChild variant="destructive" size="sm"><Link href="/emergency">I’m being threatened</Link></Button>
          <details className="relative md:hidden">
            <summary className="grid size-9 cursor-pointer list-none place-items-center rounded-lg border bg-white" aria-label="Open navigation"><Menu className="size-4" /></summary>
            <nav className="absolute right-0 top-11 w-52 rounded-xl border bg-white p-2 shadow-xl" aria-label="Mobile navigation">
              {navigation.map((item) => <Link key={item.href} href={item.href} className="block rounded-lg px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-100">{item.label}</Link>)}
            </nav>
          </details>
        </div>
      </div>
    </header>
  );
}
