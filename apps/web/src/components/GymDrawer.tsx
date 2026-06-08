"use client";

import { useState } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Gym, GymAnalysis } from "@/lib/api";

interface Props {
  gym: Gym;
  gymAnalysis: GymAnalysis | null;
  loading: boolean;
  onClose: () => void;
}

const TABS = [
  "Overview",
  "Performance",
  "Members",
  "Financials",
  "Operations",
  "Real Estate",
  "Notes & Files",
] as const;
type Tab = (typeof TABS)[number];

function FakeBadge() {
  return (
    <span className="text-amber-400/50 text-[10px] font-bold ml-0.5 select-none">
      *
    </span>
  );
}

function Sparkline({ color = "#3b82f6" }: { color?: string }) {
  return (
    <svg width="60" height="20" viewBox="0 0 60 20" className="shrink-0">
      <polyline
        points="0,16 10,12 20,14 30,6 40,8 50,4 60,3"
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
        opacity="0.8"
      />
    </svg>
  );
}

function formatOpenDate(d: string): string {
  const [year, month] = d.split("-").map(Number);
  return new Date(year, month - 1).toLocaleString("default", {
    month: "short",
    year: "numeric",
  });
}

const AMENITIES = [
  "Group Fitness",
  "Personal Training",
  "Recovery Room",
  "Childcare",
  "Tanning",
  "Sauna",
];

export default function GymDrawer({
  gym,
  gymAnalysis,
  loading,
  onClose,
}: Props) {
  const [activeTab, setActiveTab] = useState<Tab>("Overview");

  const openDate = gymAnalysis?.open_date
    ? formatOpenDate(gymAnalysis.open_date)
    : null;
  const population = gymAnalysis?.trade_area.population;
  const medianAge = gymAnalysis?.trade_area.median_age;
  const medianIncome = gymAnalysis?.trade_area.median_income;

  return (
    <div
      className="absolute bottom-0 left-0 right-0 z-10 bg-[#0D1B2A] border-t border-white/10 flex flex-col"
      style={{ height: 260 }}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-white/10 shrink-0">
        <div className="flex items-center gap-2 min-w-0">
          <span className="text-white font-semibold text-sm truncate">
            {gym.name.replace("EOS Fitness – ", "")}
          </span>
          <span className="inline-flex items-center gap-1 text-[10px] font-semibold px-2 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/25 shrink-0">
            Open
            {openDate && (
              <>
                {" "}
                · Since {openDate}
                <FakeBadge />
              </>
            )}
            {!openDate && !loading && <FakeBadge />}
          </span>
        </div>
        <button
          onClick={onClose}
          className="text-slate-500 hover:text-slate-300 transition-colors ml-2 shrink-0"
        >
          <X size={14} />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex items-center px-4 border-b border-white/10 shrink-0 overflow-x-auto">
        {TABS.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={cn(
              "text-[11px] font-medium px-3 py-2 border-b-2 whitespace-nowrap transition-colors",
              activeTab === tab
                ? "border-blue-400 text-blue-400"
                : "border-transparent text-slate-500 hover:text-slate-300"
            )}
          >
            {tab}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden px-3 py-2">
        {activeTab === "Overview" ? (
          <div className="flex gap-2.5 h-full">
            {/* Membership */}
            <div className="flex-1 bg-[#112236] rounded-lg p-2.5 flex flex-col justify-between min-w-0">
              <p className="text-[10px] text-slate-400 font-medium uppercase tracking-wide leading-none">
                Membership
              </p>
              <div>
                <p className="text-base font-bold text-white leading-none">
                  {gym.monthly_members.toLocaleString()}
                  <FakeBadge />
                </p>
                <p className="text-[10px] text-slate-500 mt-0.5">
                  total members
                </p>
              </div>
              <Sparkline color="#3b82f6" />
            </div>

            {/* Check-Ins 90 Days */}
            <div className="flex-1 bg-[#112236] rounded-lg p-2.5 flex flex-col justify-between min-w-0">
              <p className="text-[10px] text-slate-400 font-medium uppercase tracking-wide leading-none">
                Check-Ins (90D)
              </p>
              <div>
                <p className="text-base font-bold text-white leading-none">
                  {(gym.monthly_checkins * 3).toLocaleString()}
                  <FakeBadge />
                </p>
                <p className="text-[10px] text-slate-500 mt-0.5">
                  total check-ins
                </p>
              </div>
              <Sparkline color="#818cf8" />
            </div>

            {/* Revenue vs Plan */}
            <div className="flex-1 bg-[#112236] rounded-lg p-2.5 flex flex-col justify-between min-w-0">
              <p className="text-[10px] text-slate-400 font-medium uppercase tracking-wide leading-none">
                Revenue vs Plan (MTD)
              </p>
              <div>
                <p className="text-base font-bold text-white leading-none">
                  ${(gym.monthly_members * 35).toLocaleString()}
                  <FakeBadge />
                </p>
                <span className="inline-block text-[10px] font-semibold px-1.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-400 border border-emerald-500/25 mt-1">
                  +3.2% vs plan
                  <FakeBadge />
                </span>
              </div>
            </div>

            {/* Demographics */}
            <div className="flex-1 bg-[#112236] rounded-lg p-2.5 flex flex-col gap-1 min-w-0">
              <p className="text-[10px] text-slate-400 font-medium uppercase tracking-wide leading-none">
                Demographics
              </p>
              {loading ? (
                <p className="text-[10px] text-slate-600 mt-1">Loading…</p>
              ) : (
                <div className="flex flex-col gap-1 mt-0.5">
                  <div className="flex justify-between items-baseline gap-1">
                    <span className="text-[10px] text-slate-500 shrink-0">
                      Population
                    </span>
                    <span className="text-[10px] font-bold text-white">
                      {population
                        ? `${(population / 1000).toFixed(0)}k`
                        : "—"}
                      <FakeBadge />
                    </span>
                  </div>
                  <div className="flex justify-between items-baseline gap-1">
                    <span className="text-[10px] text-slate-500 shrink-0">
                      Median Age
                    </span>
                    <span className="text-[10px] font-bold text-white">
                      {medianAge ? `${medianAge} yrs` : "—"}
                      <FakeBadge />
                    </span>
                  </div>
                  <div className="flex justify-between items-baseline gap-1">
                    <span className="text-[10px] text-slate-500 shrink-0">
                      Med. HH Income
                    </span>
                    <span className="text-[10px] font-bold text-white">
                      {medianIncome
                        ? `$${(medianIncome / 1000).toFixed(0)}k`
                        : "—"}
                      <FakeBadge />
                    </span>
                  </div>
                  <div className="flex justify-between items-baseline gap-1">
                    <span className="text-[10px] text-slate-500 shrink-0">
                      College Edu.
                    </span>
                    <span className="text-[10px] font-bold text-white">
                      38%
                      <FakeBadge />
                    </span>
                  </div>
                </div>
              )}
            </div>

            {/* Amenity Profile */}
            <div className="flex-1 bg-[#112236] rounded-lg p-2.5 flex flex-col gap-1.5 min-w-0">
              <p className="text-[10px] text-slate-400 font-medium uppercase tracking-wide leading-none">
                Amenity Profile
              </p>
              <div className="flex flex-wrap gap-1">
                {AMENITIES.map((a) => (
                  <span
                    key={a}
                    className="text-[9px] font-medium px-1.5 py-0.5 rounded-full bg-blue-500/15 text-blue-300 border border-blue-500/20 leading-none"
                  >
                    {a}
                  </span>
                ))}
              </div>
              <button className="text-[10px] text-slate-500 hover:text-slate-300 text-left transition-colors mt-auto">
                + Add Amenity
              </button>
            </div>
          </div>
        ) : (
          <div className="flex items-center justify-center h-full text-slate-600 text-xs">
            {activeTab} — coming soon
          </div>
        )}
      </div>
    </div>
  );
}
