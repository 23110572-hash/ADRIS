import type { Metadata } from "next";
import { MapView } from "@/features/analyst/map-view";

export const metadata: Metadata = { title: "Geospatial aggregates" };

export default function AnalystMapPage() {
  return <MapView />;
}
