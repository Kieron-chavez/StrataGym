"use client";

import { useEffect, useRef } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import type { Gym } from "@/lib/api";
import type { Layer } from "@/types";

interface Props {
  gyms: Gym[];
  layers: Layer[];
  onMapClick: (lat: number, lng: number) => void;
  selectedPin: { lat: number; lng: number } | null;
}

export default function MapView({ gyms, layers, onMapClick, selectedPin }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const markersRef = useRef<mapboxgl.Marker[]>([]);
  const pinMarkerRef = useRef<mapboxgl.Marker | null>(null);

  // Init map
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    mapboxgl.accessToken = process.env.NEXT_PUBLIC_MAPBOX_TOKEN ?? "";

    const map = new mapboxgl.Map({
      container: containerRef.current,
      style: "mapbox://styles/mapbox/dark-v11",
      center: [-111.8910, 33.4152],
      zoom: 10.5,
      attributionControl: false,
    });

    map.addControl(new mapboxgl.NavigationControl(), "bottom-right");
    map.addControl(
      new mapboxgl.AttributionControl({ compact: true }),
      "bottom-left"
    );

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Click handler
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const handleClick = (e: mapboxgl.MapMouseEvent) => {
      onMapClick(e.lngLat.lat, e.lngLat.lng);
    };

    map.on("click", handleClick);
    return () => {
      map.off("click", handleClick);
    };
  }, [onMapClick]);

  // Gym markers
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const gymLayerActive = layers.find((l) => l.id === "gym-locations")?.active ?? true;

    // Clear existing
    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];

    if (!gymLayerActive || gyms.length === 0) return;

    const addMarkers = () => {
      gyms.forEach((gym) => {
        const el = document.createElement("div");
        el.style.cssText = `
          width: 18px;
          height: 18px;
          border-radius: 50%;
          background: #3B82F6;
          border: 2.5px solid #fff;
          box-shadow: 0 0 0 3px rgba(59,130,246,0.4);
          cursor: pointer;
        `;

        const popup = new mapboxgl.Popup({
          offset: 12,
          closeButton: false,
          className: "gym-popup",
        }).setHTML(`
          <div style="background:#112236;color:#e2e8f0;padding:10px 12px;border-radius:8px;font-family:inherit;font-size:12px;min-width:160px;">
            <div style="font-weight:600;margin-bottom:6px;color:#fff">${gym.name}</div>
            <div style="color:#94a3b8;margin-bottom:2px">Members: <span style="color:#60a5fa">${gym.monthly_members.toLocaleString()}</span></div>
            <div style="color:#94a3b8">Check-ins: <span style="color:#60a5fa">${gym.monthly_checkins.toLocaleString()}</span></div>
          </div>
        `);

        const marker = new mapboxgl.Marker({ element: el })
          .setLngLat([gym.lng, gym.lat])
          .setPopup(popup)
          .addTo(map);

        el.addEventListener("mouseenter", () => marker.togglePopup());
        el.addEventListener("mouseleave", () => {
          if (marker.getPopup()?.isOpen()) marker.togglePopup();
        });

        markersRef.current.push(marker);
      });
    };

    if (map.isStyleLoaded()) {
      addMarkers();
    } else {
      map.once("load", addMarkers);
    }

    return () => {
      markersRef.current.forEach((m) => m.remove());
      markersRef.current = [];
    };
  }, [gyms, layers]);

  // Selected pin marker
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    pinMarkerRef.current?.remove();

    if (!selectedPin) return;

    const el = document.createElement("div");
    el.style.cssText = `
      width: 20px;
      height: 20px;
      border-radius: 50%;
      background: #f59e0b;
      border: 2.5px solid #fff;
      box-shadow: 0 0 0 4px rgba(245,158,11,0.35), 0 0 16px rgba(245,158,11,0.4);
    `;

    pinMarkerRef.current = new mapboxgl.Marker({ element: el })
      .setLngLat([selectedPin.lng, selectedPin.lat])
      .addTo(map);
  }, [selectedPin]);

  return (
    <div ref={containerRef} className="flex-1 relative h-full" />
  );
}
