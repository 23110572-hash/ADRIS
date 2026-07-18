import type { Metadata, Viewport } from "next";
import { ClerkProvider } from "@clerk/nextjs";
import { AppProviders } from "@/app/providers";
import { PwaRegistration } from "@/components/pwa-registration";
import { SiteFooter } from "@/components/site-footer";
import { SiteHeader } from "@/components/site-header";
import "maplibre-gl/dist/maplibre-gl.css";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "ADRIS — Digital Fraud Safety", template: "%s | ADRIS" },
  description: "Assess suspicious digital content, preserve evidence, and get reviewed safety guidance.",
  manifest: "/manifest.webmanifest",
  applicationName: "ADRIS",
};

export const viewport: Viewport = { themeColor: "#0b6b4f", width: "device-width", initialScale: 1 };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  const app = (
    <AppProviders>
      <PwaRegistration />
      <SiteHeader />
      <main className="flex-1">{children}</main>
      <SiteFooter />
    </AppProviders>
  );
  const publishableKey = process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY;

  return (
    <html lang="en-IN">
      <body className="flex min-h-screen flex-col">{publishableKey ? <ClerkProvider publishableKey={publishableKey}>{app}</ClerkProvider> : app}</body>
    </html>
  );
}
