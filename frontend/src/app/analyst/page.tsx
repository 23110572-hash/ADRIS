import type { Metadata } from "next";
import { AnalystDashboard } from "@/features/analyst/dashboard";

export const metadata: Metadata = { title: "Analyst overview" };

export default function AnalystPage() {
  return <AnalystDashboard />;
}
