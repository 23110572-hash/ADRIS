import type { Metadata } from "next";
import { ExportsHistory } from "@/features/analyst/history-view";

export const metadata: Metadata = { title: "Evidence exports" };

export default function AnalystExportsPage() {
  return <ExportsHistory />;
}
