"use client";

import { useEffect, useRef } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import type { Gym, CensusTract, Competitor } from "@/lib/api";
import type { Layer } from "@/types";

interface Props {
  gyms: Gym[];
  layers: Layer[];
  onMapClick: (lat: number, lng: number) => void;
  selectedPin: { lat: number; lng: number } | null;
}

// Remove a GL layer/source if present — guard against uninitialized or removed map
function removeLayers(map: mapboxgl.Map, layerIds: string[], sourceId: string) {
  try {
    layerIds.forEach((id) => { if (map.getLayer(id)) map.removeLayer(id); });
    if (map.getSource(sourceId)) map.removeSource(sourceId);
  } catch {
    // style not loaded yet or map was removed — nothing to clean up
  }
}

// Insert new layers just below the first symbol (label) layer so fills sit under text
function beforeSymbol(map: mapboxgl.Map): string | undefined {
  return (map.getStyle().layers as Array<{ id: string; type: string }>)
    .find((l) => l.type === "symbol")?.id;
}

export default function MapView({ gyms, layers, onMapClick, selectedPin }: Props) {
  const containerRef  = useRef<HTMLDivElement>(null);
  const mapRef        = useRef<mapboxgl.Map | null>(null);
  const markersRef    = useRef<mapboxgl.Marker[]>([]);
  const pinMarkerRef  = useRef<mapboxgl.Marker | null>(null);
  const competitorMarkersRef = useRef<mapboxgl.Marker[]>([]);

  // Caches — populated eagerly on load; prevents re-fetching on every layer toggle
  const driveTimeGeojsonRef = useRef<object | null>(null);
  const censusTractsRef     = useRef<CensusTract[] | null>(null);
  const competitorDataRef   = useRef<Competitor[] | null>(null);

  // ── Eager pre-fetch census + competitor data once map is ready ──────────────
  // Drive-time isochrones (44 calls) stay lazy — only fetched when that layer is toggled.
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

    const prefetch = async () => {
      if (!censusTractsRef.current) {
        const data = await fetch(`${API_BASE}/api/census-density`)
          .then((r) => r.json()).catch(() => null);
        if (data?.tracts) censusTractsRef.current = data.tracts as CensusTract[];
      }
      if (!competitorDataRef.current) {
        const data = await fetch(`${API_BASE}/api/competitors`)
          .then((r) => r.json()).catch(() => null);
        if (data?.competitors) competitorDataRef.current = data.competitors as Competitor[];
      }
    };

    map.isStyleLoaded() ? prefetch() : map.once("load", prefetch);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Init map ────────────────────────────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    mapboxgl.accessToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN ?? "";

    const map = new mapboxgl.Map({
      container: containerRef.current,
      style: "mapbox://styles/mapbox/dark-v11",
      center: [-111.891, 33.4152],
      zoom: 10.5,
      attributionControl: false,
    });

    map.addControl(new mapboxgl.NavigationControl(), "bottom-right");
    map.addControl(new mapboxgl.AttributionControl({ compact: true }), "bottom-left");

    mapRef.current = map;
    return () => { map.remove(); mapRef.current = null; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Map click ───────────────────────────────────────────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const handleClick = (e: mapboxgl.MapMouseEvent) => onMapClick(e.lngLat.lat, e.lngLat.lng);
    map.on("click", handleClick);
    return () => { map.off("click", handleClick); };
  }, [onMapClick]);

  // ── EOS gym markers ─────────────────────────────────────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const active = layers.find((l) => l.id === "gym-locations")?.active ?? true;
    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];
    if (!active || !gyms.length) return;

    const add = () => {
      gyms.forEach((gym) => {
        const el = Object.assign(document.createElement("div"), { style: "" });
        el.style.cssText = `width:18px;height:18px;border-radius:50%;background:#3B82F6;
          border:2.5px solid #fff;box-shadow:0 0 0 3px rgba(59,130,246,0.4);cursor:pointer;`;

        const popup = new mapboxgl.Popup({ offset: 12, closeButton: false }).setHTML(`
          <div style="background:#112236;color:#e2e8f0;padding:10px 12px;border-radius:8px;
                      font-family:inherit;font-size:12px;min-width:160px;">
            <div style="font-weight:600;margin-bottom:6px;color:#fff">${gym.name}</div>
            <div style="color:#94a3b8;margin-bottom:2px">Members:
              <span style="color:#60a5fa">${gym.monthly_members.toLocaleString()}</span></div>
            <div style="color:#94a3b8">Check-ins:
              <span style="color:#60a5fa">${gym.monthly_checkins.toLocaleString()}</span></div>
            ${gym.rating ? `<div style="color:#94a3b8;margin-top:2px">★ ${gym.rating}</div>` : ""}
          </div>`);

        const marker = new mapboxgl.Marker({ element: el })
          .setLngLat([gym.lng, gym.lat]).setPopup(popup).addTo(map);
        el.addEventListener("mouseenter", () => marker.togglePopup());
        el.addEventListener("mouseleave", () => { if (marker.getPopup()?.isOpen()) marker.togglePopup(); });
        markersRef.current.push(marker);
      });
    };

    map.isStyleLoaded() ? add() : map.once("load", add);
    return () => { markersRef.current.forEach((m) => m.remove()); markersRef.current = []; };
  }, [gyms, layers]);

  // ── Candidate pin ───────────────────────────────────────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    pinMarkerRef.current?.remove();
    if (!selectedPin) return;

    const el = document.createElement("div");
    el.style.cssText = `width:20px;height:20px;border-radius:50%;background:#f59e0b;
      border:2.5px solid #fff;box-shadow:0 0 0 4px rgba(245,158,11,0.35),0 0 16px rgba(245,158,11,0.4);`;
    pinMarkerRef.current = new mapboxgl.Marker({ element: el })
      .setLngLat([selectedPin.lng, selectedPin.lat]).addTo(map);
  }, [selectedPin]);

  // ── Drive time — gym trade areas (15-min isochrones) ────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    let cancelled = false;

    const active = layers.find((l) => l.id === "drive-time")?.active;
    const token  = process.env.NEXT_PUBLIC_MAPBOX_TOKEN ?? "";
    const SRC = "sg-drive-time"; const FILL = "sg-dt-fill"; const LINE = "sg-dt-line";
    const clean = () => removeLayers(map, [FILL, LINE], SRC);

    const run = async () => {
      if (!active || !gyms.length) { clean(); return; }

      let geojson = driveTimeGeojsonRef.current;

      if (!geojson) {
        const results = await Promise.allSettled(
          gyms.map((g) =>
            fetch(`https://api.mapbox.com/isochrone/v1/mapbox/driving/${g.lng},${g.lat}` +
                  `?contours_minutes=15&polygons=true&access_token=${token}`)
              .then((r) => r.json())
          )
        );
        if (cancelled) return;
        const features = results
          .filter((r): r is PromiseFulfilledResult<{ features?: unknown[] }> => r.status === "fulfilled")
          .flatMap((r) => (r.value?.features as object[]) ?? []);
        geojson = { type: "FeatureCollection", features };
        driveTimeGeojsonRef.current = geojson;
      }

      if (cancelled) return;
      clean();
      const before = beforeSymbol(map);
      try {
        map.addSource(SRC, { type: "geojson", data: geojson as object as GeoJSON.FeatureCollection });
        map.addLayer({ id: FILL, type: "fill",   source: SRC, paint: { "fill-color": "#06B6D4", "fill-opacity": 0.07 } }, before);
        map.addLayer({ id: LINE, type: "line",   source: SRC, paint: { "line-color": "#06B6D4", "line-width": 1, "line-opacity": 0.35 } }, before);
      } catch { /* concurrent run beat us here */ }
    };

    map.isStyleLoaded() ? run() : map.once("load", run);
    return () => { cancelled = true; clean(); };
  }, [layers, gyms]);

  // ── Drive time — candidate pin trade area ───────────────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    let cancelled = false;

    const active = layers.find((l) => l.id === "drive-time")?.active;
    const token  = process.env.NEXT_PUBLIC_MAPBOX_TOKEN ?? "";
    const SRC = "sg-dt-cand"; const FILL = "sg-dt-cand-fill"; const LINE = "sg-dt-cand-line";
    const clean = () => removeLayers(map, [FILL, LINE], SRC);

    const run = async () => {
      clean();
      if (!active || !selectedPin) return;
      const data = await fetch(
        `https://api.mapbox.com/isochrone/v1/mapbox/driving/${selectedPin.lng},${selectedPin.lat}` +
        `?contours_minutes=15&polygons=true&access_token=${token}`
      ).then((r) => r.json()).catch(() => null);
      if (cancelled || !data || !map.isStyleLoaded()) return;

      clean(); // guard: remove any source a concurrent run added while we were fetching
      const before = beforeSymbol(map);
      try {
        map.addSource(SRC, { type: "geojson", data });
        map.addLayer({ id: FILL, type: "fill", source: SRC, paint: { "fill-color": "#F59E0B", "fill-opacity": 0.14 } }, before);
        map.addLayer({ id: LINE, type: "line", source: SRC, paint: { "line-color": "#F59E0B", "line-width": 1.5, "line-opacity": 0.6 } }, before);
      } catch { /* concurrent run beat us here */ }
    };

    map.isStyleLoaded() ? run() : map.once("load", run);
    return () => { cancelled = true; clean(); };
  }, [layers, selectedPin]);

  // ── Competitors layer ───────────────────────────────────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const active = layers.find((l) => l.id === "competitors")?.active;
    competitorMarkersRef.current.forEach((m) => m.remove());
    competitorMarkersRef.current = [];
    if (!active) return;

    const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

    const render = (competitors: Competitor[]) => {
      competitors.forEach((c) => {
        const el = document.createElement("div");
        el.style.cssText = `width:13px;height:13px;border-radius:50%;background:#F97316;
          border:2px solid #fff;box-shadow:0 0 0 2px rgba(249,115,22,0.4);cursor:pointer;`;

        const popup = new mapboxgl.Popup({ offset: 10, closeButton: false }).setHTML(`
          <div style="background:#112236;color:#e2e8f0;padding:8px 10px;border-radius:8px;
                      font-size:11px;min-width:140px;">
            <div style="font-weight:600;color:#f97316;margin-bottom:3px">Competitor</div>
            <div style="color:#fff">${c.name}</div>
            ${c.rating ? `<div style="color:#94a3b8;margin-top:2px">★ ${c.rating}</div>` : ""}
          </div>`);

        const marker = new mapboxgl.Marker({ element: el })
          .setLngLat([c.lng, c.lat]).setPopup(popup).addTo(map);
        el.addEventListener("mouseenter", () => marker.togglePopup());
        el.addEventListener("mouseleave", () => { if (marker.getPopup()?.isOpen()) marker.togglePopup(); });
        competitorMarkersRef.current.push(marker);
      });
    };

    if (competitorDataRef.current) {
      render(competitorDataRef.current);
    } else {
      fetch(`${API_BASE}/api/competitors`)
        .then((r) => r.json())
        .then((data) => {
          competitorDataRef.current = data.competitors as Competitor[];
          render(competitorDataRef.current);
        })
        .catch(console.error);
    }

    return () => { competitorMarkersRef.current.forEach((m) => m.remove()); competitorMarkersRef.current = []; };
  }, [layers]);

  // ── Population / member-density layer ──────────────────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const active   = layers.find((l) => l.id === "member-density")?.active;
    const SRC      = "sg-population"; const LAYER = "sg-pop-circles";
    const clean    = () => removeLayers(map, [LAYER], SRC);
    const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

    const apply = (tracts: CensusTract[]) => {
      clean();
      const geojson = {
        type: "FeatureCollection" as const,
        features: tracts.map((t) => ({
          type: "Feature" as const,
          geometry: { type: "Point" as const, coordinates: [t.lng, t.lat] },
          properties: { pop: t.population, score: t.pct_age_18_34 },
        })),
      };
      const before = beforeSymbol(map);
      map.addSource(SRC, { type: "geojson", data: geojson });
      map.addLayer({
        id: LAYER, type: "circle", source: SRC,
        paint: {
          "circle-radius": ["interpolate", ["linear"], ["get", "pop"], 0, 3, 4000, 7, 10000, 13, 20000, 20],
          "circle-color":  ["interpolate", ["linear"], ["get", "score"],
            0,    "#0f2942",
            0.15, "#1d4ed8",
            0.25, "#3b82f6",
            0.35, "#06b6d4",
          ],
          "circle-opacity": 0.55,
          "circle-stroke-width": 0,
        },
      }, before);
    };

    const run = async () => {
      if (!active) { clean(); return; }
      if (censusTractsRef.current) { apply(censusTractsRef.current); return; }
      const data = await fetch(`${API_BASE}/api/census-density`).then((r) => r.json()).catch(() => null);
      if (!data?.tracts || !map.isStyleLoaded()) return;
      censusTractsRef.current = data.tracts;
      apply(data.tracts);
    };

    map.isStyleLoaded() ? run() : map.once("load", run);
    return clean;
  }, [layers]);

  return <div ref={containerRef} className="flex-1 relative h-full" />;
}
