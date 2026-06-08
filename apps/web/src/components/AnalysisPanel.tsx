"use client";

import { Fragment } from "react";
import {
  ChevronRight,
  X,
  MapPin,
  TrendingUp,
  AlertTriangle,
  Activity,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { ScoreResult } from "@/lib/api";

interface Props {
  isOpen: boolean;
  loading: boolean;
  scoreResult?: ScoreResult | null;
  onClose: () => void;
}

// ── Shared atoms ─────────────────────────────────────────────────────────────

function StatCard({
  icon,
  label,
  value,
  sub,
  accent,
  fake,
}: {
  icon: React.ReactNode;
  label: string;
  value: string | number;
  sub?: string;
  accent?: string;
  fake?: boolean;
}) {
  return (
    <div className="bg-[#112236] rounded-xl p-4 flex flex-col gap-1.5">
      <div className="flex items-center gap-2 text-slate-400 text-xs font-medium">
        {icon}
        {label}
      </div>
      <div className={cn("text-2xl font-bold", accent ?? "text-white")}>
        {value}{fake && <FakeBadge />}
      </div>
      {sub && <div className="text-xs text-slate-500">{sub}</div>}
    </div>
  );
}

function FakeBadge() {
  return <span className="text-amber-400/50 text-[10px] font-bold ml-0.5 select-none">*</span>;
}

function LoadingSpinner({ label = "Loading…" }: { label?: string }) {
  return (
    <div className="flex flex-col items-center justify-center h-48 gap-3">
      <div className="w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full animate-spin" />
      <p className="text-sm text-slate-400">{label}</p>
    </div>
  );
}

// ── Site Opportunity view (proposed site click) ───────────────────────────────


function SiteOpportunityView({
  result,
  loading,
}: {
  result: ScoreResult | null;
  loading: boolean;
}) {
  if (loading) return <LoadingSpinner label="Scoring location…" />;

  if (!result) {
    return (
      <div className="flex flex-col items-center justify-center h-48 gap-3 text-center">
        <MapPin size={32} className="text-slate-600" />
        <p className="text-sm text-slate-400 leading-relaxed">
          Click anywhere on the map to score a site
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-1.5 text-xs text-slate-500">
        <MapPin size={11} />
        <span>{result.lat.toFixed(4)}, {result.lng.toFixed(4)}</span>
      </div>

      <div className="grid grid-cols-2 gap-3">
        <StatCard
          icon={<Activity size={12} />}
          label="Opportunity Score"
          value={result.opportunity_score}
          sub="Top 20% of candidates"
          accent={
            result.opportunity_score >= 75
              ? "text-green-400"
              : result.opportunity_score >= 50
              ? "text-amber-400"
              : "text-red-400"
          }
          fake
        />
        <StatCard
          icon={<TrendingUp size={12} />}
          label="Proj. Check-ins"
          value={result.projected_checkins.toLocaleString()}
          sub="per month"
          accent="text-blue-400"
          fake
        />
        <StatCard
          icon={<AlertTriangle size={12} />}
          label="Cannibalization"
          value={`${result.cannibalization_risk}%`}
          sub="member overlap"
          accent={result.cannibalization_risk > 30 ? "text-red-400" : "text-amber-400"}
          fake
        />
        <StatCard
          icon={<Activity size={12} />}
          label="Net Network Impact"
          value={`+${result.net_network_impact.toLocaleString()}`}
          sub="check-ins / month"
          accent="text-green-400"
          fake
        />
      </div>

      {result.nearby_gyms.length > 0 && (
        <>
          <div className="bg-[#112236] rounded-xl p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-3">
              Nearby Locations
            </p>
            <div className="flex flex-col gap-2">
              {result.nearby_gyms.map((gym) => (
                <div key={gym.gym_id} className="flex items-center justify-between">
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

          <div className="bg-[#112236] rounded-xl p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-3">
              Nearby Affected Gyms
            </p>
            <div className="grid grid-cols-[1fr_auto_auto_auto] gap-x-3 gap-y-2 items-baseline">
              <span className="text-[10px] text-slate-500 font-medium">Gym</span>
              <span className="text-[10px] text-slate-500 font-medium text-right">Dist.</span>
              <span className="text-[10px] text-slate-500 font-medium text-right">Cannib.</span>
              <span className="text-[10px] text-slate-500 font-medium text-right">Impact</span>
              {result.nearby_gyms.map((gym) => {
                const cannibal = Math.max(5, Math.round(38 - gym.distance_miles * 7));
                const impact = Math.abs(Math.round((6.5 - gym.distance_miles) * 260));
                return (
                  <Fragment key={gym.gym_id}>
                    <span className="text-xs text-slate-300 truncate leading-none">
                      {gym.name.replace("EOS Fitness – ", "")}
                    </span>
                    <span className="text-xs text-slate-500 tabular-nums text-right">
                      {gym.distance_miles} mi
                    </span>
                    <span className="text-xs text-amber-400 tabular-nums text-right">
                      {cannibal}%<FakeBadge />
                    </span>
                    <span className="text-xs text-red-400 tabular-nums text-right font-medium">
                      -{impact.toLocaleString()}<FakeBadge />
                    </span>
                  </Fragment>
                );
              })}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

// ── Main panel ────────────────────────────────────────────────────────────────

export default function AnalysisPanel({
  isOpen,
  loading,
  scoreResult,
  onClose,
}: Props) {
  return (
    <div
      className={cn(
        "flex flex-col w-[320px] min-h-screen bg-[#0D1B2A] border-l border-white/5 shrink-0 transition-all duration-300 overflow-hidden",
        isOpen ? "translate-x-0" : "translate-x-full w-0"
      )}
    >
      <div className="flex items-center justify-between px-5 py-4 border-b border-white/5">
        <div className="flex items-center gap-2">
          <Activity size={16} className="text-blue-400" />
          <span className="text-white font-semibold text-sm">Site Opportunity</span>
        </div>
        <button onClick={onClose} className="text-slate-500 hover:text-slate-300 transition-colors">
          <X size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4">
        <SiteOpportunityView result={scoreResult ?? null} loading={loading} />
      </div>
    </div>
  );
}

export function AnalysisPanelToggle({
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