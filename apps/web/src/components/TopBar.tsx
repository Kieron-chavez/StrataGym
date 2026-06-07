"use client";

import { useRef, useState, useEffect } from "react";
import { Search, Layers, Check, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Layer, LayerId } from "@/types";

// The two drive-time variants are mutually exclusive
const MUTEX_PAIRS: [LayerId, LayerId][] = [["drive-time", "drive-time-25"]];

interface Props {
  layers: Layer[];
  onToggle: (id: LayerId) => void;
}

export default function TopBar({ layers, onToggle }: Props) {
  const [open, setOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (!dropdownRef.current?.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const activeCount = layers.filter((l) => l.active).length;

  const handleToggle = (id: LayerId) => {
    const layer = layers.find((l) => l.id === id);
    if (!layer) return;

    // If turning on a layer that is in a mutex pair, turn off its partner first
    if (!layer.active) {
      for (const [a, b] of MUTEX_PAIRS) {
        const partner = id === a ? b : id === b ? a : null;
        if (partner) {
          const partnerLayer = layers.find((l) => l.id === partner);
          if (partnerLayer?.active) onToggle(partner);
        }
      }
    }

    onToggle(id);
  };

  return (
    <div className="flex items-center gap-2 w-full bg-[#0D1B2A]/90 backdrop-blur border-b border-white/5 px-4 py-2.5 z-10 shrink-0">
      {/* Search pill — stretches to fill available space */}
      <div className="relative flex items-center w-1/2">
        <Search size={14} className="absolute left-3.5 text-slate-500 pointer-events-none" />
        <input
          type="text"
          placeholder="Search location or gym"
          className="pl-9 pr-4 py-1.5 rounded-full bg-[#0D1B2A] border border-white/10 text-sm text-slate-300 placeholder-slate-500 focus:outline-none focus:border-white/20 w-full transition-colors"
        />
      </div>

      {/* Layers dropdown */}
      <div ref={dropdownRef} className="relative shrink-0">
        <button
          onClick={() => setOpen((v) => !v)}
          className={cn(
            "flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-medium transition-all border",
            open
              ? "bg-white/10 text-white border-white/15"
              : "text-slate-400 border-white/10 hover:bg-white/10 hover:text-slate-200"
          )}
        >
          <Layers size={13} />
          <span>Layers</span>
          {activeCount > 0 && (
            <span className="flex items-center justify-center w-4 h-4 rounded-full bg-blue-500 text-white text-[10px] font-semibold leading-none">
              {activeCount}
            </span>
          )}
          <ChevronDown
            size={12}
            className={cn("text-slate-500 transition-transform", open && "rotate-180")}
          />
        </button>

        {open && (
          <div className="absolute right-0 mt-1.5 w-52 bg-[#0D1B2A] border border-white/10 rounded-xl shadow-2xl shadow-black/50 overflow-hidden">
            <div className="px-3 py-2 border-b border-white/5">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-widest">
                Map Layers
              </p>
            </div>
            <div className="p-1.5 flex flex-col gap-0.5">
              {layers.map((layer) => {
                  return (
                  <button
                    key={layer.id}
                    onClick={() => handleToggle(layer.id)}
                    className={cn(
                      "flex items-center justify-between px-3 py-2 rounded-lg text-sm transition-all w-full text-left",
                      layer.active
                        ? "bg-blue-500/15 text-blue-300"
                        : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
                    )}
                  >
                    <span className="font-medium">{layer.label}</span>
                    <span
                      className={cn(
                        "w-4 h-4 rounded flex items-center justify-center border shrink-0 transition-all",
                        layer.active
                          ? "bg-blue-500 border-blue-500"
                          : "border-white/20"
                      )}
                    >
                      {layer.active && <Check size={10} strokeWidth={3} className="text-white" />}
                    </span>
                  </button>
                );
              })}
            </div>
            <div className="px-3 py-2 border-t border-white/5">
              <p className="text-[10px] text-slate-600 leading-tight">
                Drive Time 10 min &amp; 25 min cannot be active together.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
