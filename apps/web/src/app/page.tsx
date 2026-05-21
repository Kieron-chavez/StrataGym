"use client";

import { useEffect, useState, useCallback } from "react";
import dynamic from "next/dynamic";
import Sidebar from "@/components/Sidebar";
import LayerToggleBar from "@/components/LayerToggleBar";
import SiteOpportunityPanel, {
  PanelToggleButton,
} from "@/components/SiteOpportunityPanel";
import { fetchGyms, scoreLocation } from "@/lib/api";
import type { Gym, ScoreResult } from "@/lib/api";
import type { Layer, LayerId } from "@/types";

const MapView = dynamic(() => import("@/components/MapView"), { ssr: false });

const INITIAL_LAYERS: Layer[] = [
  { id: "gym-locations", label: "Gym Locations", active: true },
  { id: "member-density", label: "Member Density", active: false },
  { id: "drive-time", label: "Drive Time", active: false },
  { id: "competitors", label: "Competitors", active: false },
];

export default function DashboardPage() {
  const [gyms, setGyms] = useState<Gym[]>([]);
  const [layers, setLayers] = useState<Layer[]>(INITIAL_LAYERS);
  const [scoreResult, setScoreResult] = useState<ScoreResult | null>(null);
  const [scoring, setScoring] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);
  const [selectedPin, setSelectedPin] = useState<{
    lat: number;
    lng: number;
  } | null>(null);

  useEffect(() => {
    fetchGyms()
      .then(setGyms)
      .catch((err) => console.error("Failed to load gyms:", err));
  }, []);

  const handleToggleLayer = useCallback((id: LayerId) => {
    setLayers((prev) =>
      prev.map((l) => (l.id === id ? { ...l, active: !l.active } : l))
    );
  }, []);

  const handleMapClick = useCallback(async (lat: number, lng: number) => {
    setSelectedPin({ lat, lng });
    setPanelOpen(true);
    setScoring(true);
    setScoreResult(null);

    try {
      const result = await scoreLocation(lat, lng);
      setScoreResult(result);
    } catch (err) {
      console.error("Failed to score location:", err);
    } finally {
      setScoring(false);
    }
  }, []);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#0D1B2A]">
      {/* Sidebar */}
      <Sidebar />

      {/* Map area */}
      <div className="relative flex-1 flex flex-col">
        {/* Layer toggle bar */}
        <LayerToggleBar layers={layers} onToggle={handleToggleLayer} />

        {/* Map */}
        <MapView
          gyms={gyms}
          layers={layers}
          onMapClick={handleMapClick}
          selectedPin={selectedPin}
        />

        {/* Panel toggle button (visible when panel is closed) */}
        {!panelOpen && (
          <div className="absolute right-0 top-1/2 -translate-y-1/2 z-10">
            <PanelToggleButton
              isOpen={false}
              onClick={() => setPanelOpen(true)}
            />
          </div>
        )}
      </div>

      {/* Right panel */}
      {panelOpen && (
        <SiteOpportunityPanel
          result={scoreResult}
          loading={scoring}
          isOpen={panelOpen}
          onClose={() => setPanelOpen(false)}
        />
      )}
    </div>
  );
}
