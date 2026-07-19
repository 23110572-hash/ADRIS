"use client";

import { SignInButton, useAuth } from "@clerk/nextjs";
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { LockKeyhole, LoaderCircle, Settings } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const TokenContext = createContext<string | null>(null);

function ClerkSession({ children }: { children: ReactNode }) {
  const { isLoaded, isSignedIn, getToken } = useAuth();
  const [token, setToken] = useState<string | null>(null);
  const [tokenError, setTokenError] = useState<string | null>(null);
  useEffect(() => {
    if (!isLoaded || !isSignedIn) return;
    const template = process.env.NEXT_PUBLIC_CLERK_JWT_TEMPLATE || "adris-api";
    getToken({ template })
      .then((value) => {
        if (!value) {
          setTokenError("Clerk returned no API token");
          return;
        }
        setToken(value);
      })
      .catch((error: unknown) => setTokenError(error instanceof Error ? error.message : "Could not obtain API token"));
  }, [getToken, isLoaded, isSignedIn]);
  if (!isLoaded) return <div className="grid min-h-64 place-items-center"><LoaderCircle className="size-7 animate-spin text-emerald-800" /></div>;
  if (!isSignedIn) return <Card className="mx-auto max-w-xl"><CardHeader><CardTitle className="flex items-center gap-2"><LockKeyhole className="size-5" /> Analyst sign-in required</CardTitle></CardHeader><CardContent><p className="mb-5 text-sm leading-6 text-slate-600">Protected evidence and review tools require a Clerk account with an ADRIS analyst role and MFA.</p><SignInButton mode="modal"><Button>Sign in with Clerk</Button></SignInButton></CardContent></Card>;
  if (tokenError) return <Card className="border-red-200"><CardHeader><CardTitle>API token unavailable</CardTitle></CardHeader><CardContent className="text-sm text-red-800">{tokenError}. Configure the <code>adris-api</code> Clerk JWT template and role claims.</CardContent></Card>;
  if (!token) return <div className="grid min-h-64 place-items-center"><LoaderCircle className="size-7 animate-spin text-emerald-800" /></div>;
  return <TokenContext.Provider value={token}>{children}</TokenContext.Provider>;
}

export function AnalystAccess({ children }: { children: ReactNode }) {
  if (!process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY) {
    return <Card className="mx-auto max-w-xl border-amber-200"><CardHeader><CardTitle className="flex items-center gap-2"><Settings className="size-5" /> Clerk configuration required</CardTitle></CardHeader><CardContent className="space-y-3 text-sm leading-6 text-slate-700"><p>The analyst console is intentionally unavailable without authentication. Add the Clerk publishable key to the frontend and JWKS/JWT settings to FastAPI.</p><p>Frontend route hiding is not the security boundary: every analyst API endpoint also verifies the JWT, role, and production MFA claim.</p></CardContent></Card>;
  }
  return <ClerkSession>{children}</ClerkSession>;
}

export function useAnalystToken(): string {
  const token = useContext(TokenContext);
  if (!token) throw new Error("Analyst token is unavailable outside the authenticated analyst boundary");
  return token;
}
