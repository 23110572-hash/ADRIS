import type { Metadata } from "next";
import { QueueView } from "@/features/analyst/queue-view";

export const metadata: Metadata = { title: "Review queue" };

export default function AnalystQueuePage() {
  return <QueueView />;
}
