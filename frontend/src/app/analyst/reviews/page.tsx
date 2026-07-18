import type { Metadata } from "next";
import { ReviewsHistory } from "@/features/analyst/history-view";

export const metadata: Metadata = { title: "Review history" };

export default function AnalystReviewsPage() {
  return <ReviewsHistory />;
}
