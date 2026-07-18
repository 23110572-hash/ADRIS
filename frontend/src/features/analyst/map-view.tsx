"use client";

import { useQuery } from "@tanstack/react-query";
import maplibregl from "maplibre-gl";
import { useEffect, useRef } from "react";
import { ApiErrorState } from "@/components/api-error";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getMapData } from "@/features/analyst/api";
import { useAnalystToken } from "@/features/analyst/access";

export function MapView() {
  const token = useAnalystToken();
  const container = useRef<HTMLDivElement | null>(null);
  const query = useQuery({ queryKey: ["analyst-map"], queryFn: () => getMapData(token) });
  useEffect(() => {
    if (!container.current || !query.data) return;
    const map = new maplibregl.Map({ container: container.current, center: [78.9629, 22.5937], zoom: 3.4, style: { version: 8, sources: {}, layers: [{ id: "background", type: "background", paint: { "background-color": "#eef3ef" } }] } });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.on("load", () => {
      const geojson: GeoJSON.FeatureCollection<GeoJSON.Point> = { type: "FeatureCollection", features: query.data!.cells.map((cell) => ({ type: "Feature", geometry: { type: "Point", coordinates: [cell.longitude, cell.latitude] }, properties: { ...cell } })) };
      map.addSource("adris-cells", { type: "geojson", data: geojson });
      map.addLayer({ id: "adris-cells", type: "circle", source: "adris-cells", paint: { "circle-radius": ["interpolate", ["linear"], ["get", "incident_count"], 5, 8, 50, 28], "circle-color": ["interpolate", ["linear"], ["get", "high_risk_count"], 0, "#f59e0b", 10, "#b42318"], "circle-opacity": 0.78, "circle-stroke-color": "#ffffff", "circle-stroke-width": 2 } });
      map.on("click", "adris-cells", (event) => { const feature = event.features?.[0]; if (!feature) return; const props = feature.properties as Record<string, string | number>; new maplibregl.Popup().setLngLat(event.lngLat).setHTML(`<strong>${props.incident_count} reports</strong><br>${props.high_risk_count} high risk<br>${props.caution_count} caution`).addTo(map); });
      if (query.data!.cells.length) { const bounds = new maplibregl.LngLatBounds(); query.data!.cells.forEach((cell) => bounds.extend([cell.longitude, cell.latitude])); map.fitBounds(bounds, { padding: 70, maxZoom: 7 }); }
    });
    return () => map.remove();
  }, [query.data]);
  if (query.isError) return <ApiErrorState error={query.error} retry={() => query.refetch()} />;
  return <div className="grid gap-6 xl:grid-cols-[1fr_320px]"><Card className="overflow-hidden"><CardHeader><CardTitle>Privacy-preserving report density</CardTitle></CardHeader><CardContent><div ref={container} className="h-[620px] overflow-hidden rounded-xl border" /></CardContent></Card><Card className="h-fit"><CardHeader><CardTitle>Privacy boundary</CardTitle></CardHeader><CardContent className="text-sm leading-6 text-slate-600"><p>{query.data?.privacy_note ?? "Loading suppression policy…"}</p><p className="mt-4">Minimum displayed reports per cell: <strong>{query.data?.minimum_display_count ?? 5}</strong>.</p><p className="mt-4 text-xs">The map never displays exact victim locations and must not be interpreted as an offender-location map.</p></CardContent></Card></div>;
}
