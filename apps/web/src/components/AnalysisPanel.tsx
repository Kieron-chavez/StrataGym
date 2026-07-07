"use client";

import { Fragment } from "react";
import {
  ChevronRight,
  X,
  MapPin,
  TrendingUp,
  AlertTriangle,
  Activity,
  ArrowUpRight,
  ArrowDownRight,
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

  const netPositive = result.net_network_impact >= 0;

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
          sub={result.score_percentile_label}
          accent={
            result.opportunity_score >= 75
              ? "text-green-400"
              : result.opportunity_score >= 50
              ? "text-amber-400"
              : "text-red-400"
          }
        />
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
          value={`${result.cannibalization_pct}%`}
          sub={`${result.cannibalization_label} · member overlap`}
          accent={result.cannibalization_pct > 30 ? "text-red-400" : "text-amber-400"}
        />
        <StatCard
          icon={<Activity size={12} />}
          label="Net Network Impact"
          value={`${netPositive ? "+" : ""}${result.net_network_impact.toLocaleString()}`}
          sub="check-ins / month"
          accent={netPositive ? "text-green-400" : "text-red-400"}
        />
      </div>

      <div className="bg-[#112236] rounded-xl px-4 py-3 flex items-center justify-between">
        <span className="text-xs text-slate-400">Verdict</span>
        <span
          className={cn(
            "text-xs font-semibold",
            result.opportunity_score >= 75
              ? "text-green-400"
              : result.opportunity_score >= 50
              ? "text-amber-400"
              : "text-red-400"
          )}
        >
          {result.score_label}
        </span>
      </div>

      {result.score_drivers.length > 0 && (
        <div className="bg-[#112236] rounded-xl p-4">
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-3">
            Score Drivers
          </p>
          <div className="flex flex-col gap-2">
            {result.score_drivers.map((driver) => (
              <div key={driver.label} className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2 min-w-0">
                  {driver.direction === "positive" ? (
                    <ArrowUpRight size={12} className="text-green-400 shrink-0" />
                  ) : (
                    <ArrowDownRight size={12} className="text-red-400 shrink-0" />
                  )}
                  <span className="text-xs text-slate-300 truncate">{driver.label}</span>
                </div>
                <span
                  className={cn(
                    "text-xs font-semibold tabular-nums shrink-0",
                    driver.direction === "positive" ? "text-green-400" : "text-red-400"
                  )}
                >
                  {driver.points >= 0 ? "+" : ""}{driver.points} pts
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="bg-[#112236] rounded-xl p-4">
        <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-3">
          Nearby EOS Impact
        </p>
        {result.nearby_eos_locations.length === 0 ? (
          <p className="text-xs text-slate-500">No EOS locations within 5 miles</p>
        ) : (
          <div className="grid grid-cols-[1fr_auto_auto_auto] gap-x-3 gap-y-2 items-baseline">
            <span className="text-[10px] text-slate-500 font-medium">Gym</span>
            <span className="text-[10px] text-slate-500 font-medium text-right">Dist.</span>
            <span className="text-[10px] text-slate-500 font-medium text-right">Cannib.</span>
            <span className="text-[10px] text-slate-500 font-medium text-right">Impact</span>
            {result.nearby_eos_locations.map((gym) => (
              <Fragment key={gym.name}>
                <span className="text-xs text-slate-300 truncate leading-none">
                  {gym.name.replace("EOS Fitness – ", "")}
                </span>
                <span className="text-xs text-slate-500 tabular-nums text-right">
                  {gym.distance_mi} mi
                </span>
                <span className="text-xs text-amber-400 tabular-nums text-right">
                  {gym.cannibalization_pct}%
                </span>
                <span className="text-xs text-red-400 tabular-nums text-right font-medium">
                  {gym.impact.toLocaleString()}
                </span>
              </Fragment>
            ))}
          </div>
        )}
      </div>
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