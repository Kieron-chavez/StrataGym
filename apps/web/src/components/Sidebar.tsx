"use client";

import {
  Map,
  Users,
  TrendingUp,
  Target,
  Building2,
  BarChart2,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useState } from "react";

const NAV_ITEMS = [
  { id: "network-map", label: "Network Map", icon: Map },
  { id: "member-heatmap", label: "Member Heatmap", icon: Users },
  { id: "traffic-forecast", label: "Traffic Forecast", icon: TrendingUp },
  { id: "opportunity-heatmap", label: "Opportunity Heatmap", icon: Target },
  { id: "mls-overlay", label: "MLS Overlay", icon: Building2 },
  { id: "revenue-trends", label: "Revenue Trends", icon: BarChart2 },
] as const;

export default function Sidebar() {
  const [active, setActive] = useState("network-map");

  return (
    <aside className="flex flex-col w-[220px] min-h-screen bg-[#0D1B2A] border-r border-white/5 shrink-0">
      {/* Logo / brand */}
      <div className="flex items-center gap-2.5 px-5 py-5 border-b border-white/5">
        <div className="w-8 h-8 rounded-lg bg-blue-500 flex items-center justify-center shrink-0">
          <Target size={16} className="text-white" />
        </div>
        <span className="text-white font-semibold text-sm tracking-wide">
          StrataGym
        </span>
      </div>

      {/* Nav */}
      <nav className="flex flex-col gap-0.5 px-3 py-4 flex-1">
        <p className="text-[10px] font-semibold uppercase tracking-widest text-slate-500 px-2 mb-2">
          Views
        </p>
        {NAV_ITEMS.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setActive(id)}
            className={cn(
              "flex items-center gap-3 w-full px-3 py-2.5 rounded-lg text-sm font-medium transition-colors text-left",
              active === id
                ? "bg-blue-500/20 text-blue-400"
                : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
            )}
          >
            <Icon size={16} className="shrink-0" />
            {label}
          </button>
        ))}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-white/5">
        <p className="text-[11px] text-slate-600">EOS Fitness · AZ Network</p>
      </div>
    </aside>
  );
}
