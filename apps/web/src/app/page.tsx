"use client";

import { useEffect, useState, useCallback } from "react";
import dynamic from "next/dynamic";
import Sidebar from "@/components/Sidebar";
import TopBar from "@/components/TopBar";
import AnalysisPanel, {
  AnalysisPanelToggle,
} from "@/components/AnalysisPanel";
import { fetchGyms, fetchGymAnalysis, scoreLocation } from "@/lib/api";
import type { Gym, GymAnalysis, ScoreResult } from "@/lib/api";
import type { Layer, LayerId } from "@/types";

const MapView = dynamic(() => import("@/components/MapView"), { ssr: false });

const INITIAL_LAYERS: Layer[] = [
  { id: "gym-locations", label: "Gym Locations", active: true },
  { id: "member-density", label: "Member Density", active: false },
  { id: "drive-time", label: "Drive Time · 10 min", active: false },
  { id: "drive-time-25", label: "Drive Time · 25 min", active: false },
  { id: "competitors", label: "Competitors", active: false },
];

export default function DashboardPage() {
  const [gyms, setGyms] = useState<Gym[]>([]);
  const [layers, setLayers] = useState<Layer[]>(INITIAL_LAYERS);
  const [loading, setLoading] = useState(false);
  const [panelOpen, setPanelOpen] = useState(false);

  // Mutually exclusive selection states
  const [selectedLocation, setSelectedLocation] = useState<Gym | null>(null);
  const [selectedSite, setSelectedSite] = useState<{ lat: number; lng: number } | null>(null);

  // One result type is active at a time depending on which state is set
  const [scoreResult, setScoreResult] = useState<ScoreResult | null>(null);
  const [gymAnalysis, setGymAnalysis] = useState<GymAnalysis | null>(null);

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
    setSelectedSite({ lat, lng });
    setSelectedLocation(null);
    setGymAnalysis(null);
    setScoreResult(null);
    setPanelOpen(true);
    setLoading(true);
    try {
      const result = await scoreLocation(lat, lng);
      setScoreResult(result);
    } catch (err) {
      console.error("Failed to score location:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleGymClick = useCallback(async (gym: Gym) => {
    setSelectedLocation(gym);
    setSelectedSite(null);
    setScoreResult(null);
    setGymAnalysis(null);
    setPanelOpen(true);
    setLoading(true);
    try {
      const analysis = await fetchGymAnalysis(gym.gym_id);
      setGymAnalysis(analysis);
    } catch (err) {
      console.error("Failed to fetch gym analysis:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  const handleClearSelection = useCallback(() => {
    setSelectedLocation(null);
    setSelectedSite(null);
    setScoreResult(null);
    setGymAnalysis(null);
    setPanelOpen(false);
  }, []);

  return (
    <div className="flex h-screen w-screen overflow-hidden bg-[#0D1B2A]">
      {/* Sidebar spans full height */}
      <Sidebar />

      {/* Right column: top bar + map/panel beneath */}
      <div className="flex flex-col flex-1 overflow-hidden">
        <TopBar layers={layers} onToggle={handleToggleLayer} />

        <div className="flex flex-1 overflow-hidden">
          <div className="relative flex-1">
            <MapView
              gyms={gyms}
              layers={layers}
              onMapClick={handleMapClick}
              onGymClick={handleGymClick}
              onClearSelection={handleClearSelection}
              selectedLocation={selectedLocation}
              selectedSite={selectedSite}
            />

            {!panelOpen && (
              <div className="absolute right-0 top-1/2 -translate-y-1/2 z-10">
                <AnalysisPanelToggle
                  isOpen={false}
                  onClick={() => setPanelOpen(true)}
                />
              </div>
            )}
          </div>

          {panelOpen && (
            <AnalysisPanel
              isOpen={panelOpen}
              loading={loading}
              selectedGym={selectedLocation}
              gymAnalysis={gymAnalysis}
              scoreResult={scoreResult}
              onClose={() => setPanelOpen(false)}
            />
          )}
        </div>
      </div>
    </div>
  );
}
