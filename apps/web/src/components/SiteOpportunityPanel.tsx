"use client";

import { ChevronRight, X, MapPin, TrendingUp, AlertTriangle, Activity } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ScoreResult } from "@/types";

interface Props {
  result: ScoreResult | null;
  loading: boolean;
  isOpen: boolean;
  onClose: () => void;
}

function ScoreRing({ score }: { score: number }) {
  const radius = 28;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;

  const color =
    score >= 75 ? "#22c55e" : score >= 50 ? "#f59e0b" : "#ef4444";

  return (
    <div className="relative flex items-center justify-center w-20 h-20">
      <svg width="80" height="80" className="-rotate-90">
        <circle
          cx="40"
          cy="40"
          r={radius}
          fill="none"
          stroke="#1e3a54"
          strokeWidth="6"
        />
        <circle
          cx="40"
          cy="40"
          r={radius}
          fill="none"
          stroke={color}
          strokeWidth="6"
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
        />
      </svg>
      <span
        className="absolute text-lg font-bold"
        style={{ color }}
      >
        {score}
      </span>
    </div>
  );
}

interface StatCardProps {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  sub?: string;
  accent?: string;
}

function StatCard({ icon, label, value, sub, accent }: StatCardProps) {
  return (
    <div className="bg-[#112236] rounded-xl p-4 flex flex-col gap-1.5">
      <div className="flex items-center gap-2 text-slate-400 text-xs font-medium">
        {icon}
        {label}
      </div>
      <div className={cn("text-2xl font-bold", accent ?? "text-white")}>
        {value}
      </div>
      {sub && <div className="text-xs text-slate-500">{sub}</div>}
    </div>
  );
}

export default function SiteOpportunityPanel({
  result,
  loading,
  isOpen,
  onClose,
}: Props) {
  return (
    <div
      className={cn(
        "flex flex-col w-[320px] min-h-screen bg-[#0D1B2A] border-l border-white/5 shrink-0 transition-all duration-300 overflow-hidden",
        isOpen ? "translate-x-0" : "translate-x-full w-0"
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-white/5">
        <div className="flex items-center gap-2">
          <Activity size={16} className="text-blue-400" />
          <span className="text-white font-semibold text-sm">Site Opportunity</span>
        </div>
        <button
          onClick={onClose}
          className="text-slate-500 hover:text-slate-300 transition-colors"
        >
          <X size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4">
        {loading && (
          <div className="flex flex-col items-center justify-center h-48 gap-3">
            <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
            <p className="text-sm text-slate-400">Scoring location…</p>
          </div>
        )}

        {!loading && !result && (
          <div className="flex flex-col items-center justify-center h-48 gap-3 text-center">
            <MapPin size={32} className="text-slate-600" />
            <p className="text-sm text-slate-400 leading-relaxed">
              Click anywhere on the map to score a site
            </p>
          </div>
        )}

        {!loading && result && (
          <div className="flex flex-col gap-4">
            {/* Coordinates */}
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <MapPin size={11} />
              <span>
                {result.lat.toFixed(4)}, {result.lng.toFixed(4)}
              </span>
            </div>

            {/* Opportunity Score */}
            <div className="bg-[#112236] rounded-xl p-4 flex items-center gap-4">
              <ScoreRing score={result.opportunity_score} />
              <div>
                <p className="text-xs text-slate-400 font-medium uppercase tracking-wide mb-0.5">
                  Opportunity Score
                </p>
                <p className="text-sm text-green-400 font-semibold">
                  Strong site
                </p>
                <p className="text-xs text-slate-500 mt-1">
                  Top 20% of candidates
                </p>
              </div>
            </div>

            {/* Stat grid */}
            <div className="grid grid-cols-2 gap-3">
              <StatCard
                icon={<TrendingUp size={12} />}
                label="Proj. Check-ins"
                value={result.projected_checkins.toLocaleString()}
                sub="per month"
                accent="text-blue-400"
              />
              <StatCard
                icon={<AlertTriangle size={12} />}
                label="Cannibalization"
                value={`${result.cannibalization_risk}%`}
                sub="member overlap"
                accent={
                  result.cannibalization_risk > 30
                    ? "text-red-400"
                    : "text-amber-400"
                }
              />
            </div>

            <StatCard
              icon={<Activity size={12} />}
              label="Net Network Impact"
              value={`+${result.net_network_impact.toLocaleString()}`}
              sub="incremental check-ins / month"
              accent="text-green-400"
            />

            {/* Nearby gyms */}
            {result.nearby_gyms.length > 0 && (
              <div className="bg-[#112236] rounded-xl p-4">
                <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-3">
                  Nearby Locations
                </p>
                <div className="flex flex-col gap-2">
                  {result.nearby_gyms.map((gym) => (
                    <div
                      key={gym.gym_id}
                      className="flex items-center justify-between"
                    >
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-blue-400 shrink-0" />
                        <span className="text-xs text-slate-300 leading-tight">
                          {gym.name.replace("EOS Fitness – ", "")}
                        </span>
                      </div>
                      <span className="text-xs text-slate-500 tabular-nums">
                        {gym.distance_miles} mi
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export function PanelToggleButton({
  isOpen,
  onClick,
}: {
  isOpen: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="absolute right-0 top-1/2 -translate-y-1/2 z-10 flex items-center justify-center w-6 h-12 bg-[#112236] border border-white/10 rounded-l-lg hover:bg-[#162B44] transition-colors"
    >
      <ChevronRight
        size={14}
        className={cn(
          "text-slate-400 transition-transform",
          isOpen ? "rotate-0" : "rotate-180"
        )}
      />
    </button>
  );
}
