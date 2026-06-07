"use client";

import {
  ChevronRight,
  X,
  MapPin,
  TrendingUp,
  AlertTriangle,
  Activity,
  Users,
  Calendar,
  DollarSign,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { Gym, GymAnalysis, ScoreResult } from "@/lib/api";

interface Props {
  isOpen: boolean;
  loading: boolean;
  selectedGym?: Gym | null;
  gymAnalysis?: GymAnalysis | null;
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

function ScoreRing({ score }: { score: number }) {
  const radius = 28;
  const circumference = 2 * Math.PI * radius;
  const offset = circumference - (score / 100) * circumference;
  const color = score >= 75 ? "#22c55e" : score >= 50 ? "#f59e0b" : "#ef4444";
  return (
    <div className="relative flex items-center justify-center w-20 h-20">
      <svg width="80" height="80" className="-rotate-90">
        <circle cx="40" cy="40" r={radius} fill="none" stroke="#1e3a54" strokeWidth="6" />
        <circle
          cx="40" cy="40" r={radius} fill="none"
          stroke={color} strokeWidth="6"
          strokeDasharray={circumference} strokeDashoffset={offset}
          strokeLinecap="round"
        />
      </svg>
      <span className="absolute text-lg font-bold" style={{ color }}>{score}<FakeBadge /></span>
    </div>
  );
}

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

      <div className="bg-[#112236] rounded-xl p-4 flex items-center gap-4">
        <ScoreRing score={result.opportunity_score} />
        <div>
          <p className="text-xs text-slate-400 font-medium uppercase tracking-wide mb-0.5">
            Opportunity Score
          </p>
          <p className="text-sm text-green-400 font-semibold">Strong site</p>
          <p className="text-xs text-slate-500 mt-1">Top 20% of candidates</p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3">
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
      </div>

      <StatCard
        icon={<Activity size={12} />}
        label="Net Network Impact"
        value={`+${result.net_network_impact.toLocaleString()}`}
        sub="incremental check-ins / month"
        accent="text-green-400"
        fake
      />

      {result.nearby_gyms.length > 0 && (
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
      )}
    </div>
  );
}

// ── Location Analysis view (existing EOS pin click) ───────────────────────────

const TIER_STYLES = {
  "Top Performer":  "bg-emerald-500/15 text-emerald-400 border border-emerald-500/25",
  "Average":        "bg-amber-500/15  text-amber-400  border border-amber-500/25",
  "Underperforming":"bg-red-500/15    text-red-400    border border-red-500/25",
} as const;

const TIER_LABELS = {
  "Top Performer":  "Top Performer",
  "Average":        "Average",
  "Underperforming":"Underperforming",
} as const;

function formatOpenDate(d: string): string {
  const [year, month] = d.split("-").map(Number);
  return new Date(year, month - 1).toLocaleString("default", {
    month: "long",
    year: "numeric",
  });
}

function LocationAnalysisView({
  gym,
  analysis,
  loading,
}: {
  gym: Gym;
  analysis: GymAnalysis | null;
  loading: boolean;
}) {
  return (
    <div className="flex flex-col gap-4">
      {/* Gym identity */}
      <div className="bg-[#112236] rounded-xl p-4">
        <div className="flex items-center gap-2 mb-2">
          <div className="w-2.5 h-2.5 rounded-full bg-blue-400 shrink-0" />
          <span className="text-xs font-semibold uppercase tracking-wide text-blue-400">
            Existing Location
          </span>
        </div>
        <p className="text-white font-semibold text-sm leading-snug">{gym.name}</p>
        <p className="text-slate-500 text-xs mt-1 leading-snug">{gym.address}</p>
        <div className="flex gap-4 mt-3">
          <div>
            <p className="text-xs text-slate-500">Members</p>
            <p className="text-sm font-bold text-blue-400">{gym.monthly_members.toLocaleString()}<FakeBadge /></p>
          </div>
          <div>
            <p className="text-xs text-slate-500">Check-ins/mo</p>
            <p className="text-sm font-bold text-blue-400">{gym.monthly_checkins.toLocaleString()}<FakeBadge /></p>
          </div>
          {gym.rating && (
            <div>
              <p className="text-xs text-slate-500">Rating</p>
              <p className="text-sm font-bold text-slate-200">★ {gym.rating}</p>
            </div>
          )}
        </div>
      </div>

      {/* Analysis data */}
      {loading && <LoadingSpinner label="Loading analysis…" />}

      {!loading && analysis && (
        <>
          {/* Performance tier */}
          <div className="bg-[#112236] rounded-xl p-4 flex items-center justify-between">
            <div>
              <p className="text-xs text-slate-400 font-medium uppercase tracking-wide mb-1">
                Performance Tier
              </p>
              <span
                className={cn(
                  "inline-block text-xs font-semibold px-2.5 py-1 rounded-full",
                  TIER_STYLES[analysis.performance_tier]
                )}
              >
                {TIER_LABELS[analysis.performance_tier]}<FakeBadge />
              </span>
            </div>
            <div className="text-right">
              <p className="text-xs text-slate-500">Network rank</p>
              <p className="text-lg font-bold text-white">
                {analysis.performance_rank_pct}
                <span className="text-xs text-slate-400 font-normal">th %ile</span>
                <FakeBadge />
              </p>
            </div>
          </div>

          {/* Open date */}
          <div className="flex items-center gap-3 px-4 py-3 bg-[#112236] rounded-xl">
            <Calendar size={14} className="text-slate-400 shrink-0" />
            <div>
              <p className="text-xs text-slate-500">Opened</p>
              <p className="text-sm text-white font-medium">
                {formatOpenDate(analysis.open_date)}<FakeBadge />
              </p>
            </div>
          </div>

          {/* Trade area */}
          <div className="bg-[#112236] rounded-xl p-4">
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-3">
              Trade Area · 10-Min Drive
            </p>
            <div className="grid grid-cols-3 gap-2">
              <div className="flex flex-col gap-1">
                <div className="flex items-center gap-1 text-slate-500">
                  <Users size={10} />
                  <span className="text-xs">Population</span>
                </div>
                <p className="text-sm font-bold text-white">
                  {(analysis.trade_area.population / 1000).toFixed(0)}k
                </p>
              </div>
              <div className="flex flex-col gap-1">
                <div className="flex items-center gap-1 text-slate-500">
                  <DollarSign size={10} />
                  <span className="text-xs">Med. Income</span>
                </div>
                <p className="text-sm font-bold text-white">
                  ${(analysis.trade_area.median_income / 1000).toFixed(0)}k
                </p>
              </div>
              <div className="flex flex-col gap-1">
                <div className="flex items-center gap-1 text-slate-500">
                  <Activity size={10} />
                  <span className="text-xs">Median Age</span>
                </div>
                <p className="text-sm font-bold text-white">
                  {analysis.trade_area.median_age} yrs
                </p>
              </div>
            </div>
          </div>

          {/* Nearby EOS locations */}
          {analysis.nearby_eos.length > 0 && (
            <div className="bg-[#112236] rounded-xl p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-3">
                Nearby EOS Locations
              </p>
              <div className="flex flex-col gap-2">
                {analysis.nearby_eos.map((loc) => (
                  <div key={loc.gym_id} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full bg-blue-400 shrink-0" />
                      <span className="text-xs text-slate-300 leading-tight">
                        {loc.name.replace("EOS Fitness – ", "")}
                      </span>
                    </div>
                    <span className="text-xs text-slate-500 tabular-nums">
                      {loc.distance_miles} mi
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Nearby competitors */}
          {analysis.nearby_competitors.length > 0 && (
            <div className="bg-[#112236] rounded-xl p-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-400 mb-3">
                Nearby Competitors
              </p>
              <div className="flex flex-col gap-2">
                {analysis.nearby_competitors.map((c, i) => (
                  <div key={i} className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <div className="w-2 h-2 rounded-full bg-orange-400 shrink-0" />
                      <div>
                        <span className="text-xs text-slate-300 leading-tight">{c.name}</span>
                        {c.rating && (
                          <span className="text-xs text-slate-500 ml-1.5">★ {c.rating}</span>
                        )}
                      </div>
                    </div>
                    <span className="text-xs text-slate-500 tabular-nums">
                      {c.distance_miles} mi
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {analysis.nearby_competitors.length === 0 && (
            <p className="text-xs text-slate-600 text-center py-2">
              Enable the Competitors layer to see nearby competitors
            </p>
          )}
        </>
      )}
    </div>
  );
}

// ── Main panel ────────────────────────────────────────────────────────────────

export default function AnalysisPanel({
  isOpen,
  loading,
  selectedGym,
  gymAnalysis,
  scoreResult,
  onClose,
}: Props) {
  const title = selectedGym ? "Location Analysis" : "Site Opportunity";

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
          <span className="text-white font-semibold text-sm">{title}</span>
        </div>
        <button onClick={onClose} className="text-slate-500 hover:text-slate-300 transition-colors">
          <X size={16} />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-4">
        {selectedGym ? (
          <LocationAnalysisView gym={selectedGym} analysis={gymAnalysis ?? null} loading={loading} />
        ) : (
          <SiteOpportunityView result={scoreResult ?? null} loading={loading} />
        )}
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