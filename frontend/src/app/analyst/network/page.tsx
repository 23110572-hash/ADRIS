import type { Metadata } from "next";
import { NetworkView } from "@/features/analyst/network-view";

export const metadata: Metadata = { title: "Fraud network" };

export default function AnalystNetworkPage() {
  return <NetworkView />;
}
