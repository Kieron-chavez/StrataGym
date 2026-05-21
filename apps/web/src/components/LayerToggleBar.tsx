"use client";

import { Layers } from "lucide-react";
import { cn } from "@/lib/utils";
import type { Layer, LayerId } from "@/types";

interface Props {
  layers: Layer[];
  onToggle: (id: LayerId) => void;
}

export default function LayerToggleBar({ layers, onToggle }: Props) {
  return (
    <div className="absolute top-4 left-1/2 -translate-x-1/2 z-10 flex items-center gap-1 bg-[#0D1B2A]/90 backdrop-blur border border-white/10 rounded-xl px-3 py-2 shadow-xl">
      <Layers size={14} className="text-slate-400 mr-1.5 shrink-0" />
      {layers.map((layer) => (
        <button
          key={layer.id}
          onClick={() => onToggle(layer.id)}
          className={cn(
            "px-3 py-1.5 rounded-lg text-xs font-medium transition-all",
            layer.active
              ? "bg-blue-500 text-white shadow-md shadow-blue-500/30"
              : "text-slate-400 hover:bg-white/10 hover:text-slate-200"
          )}
        >
          {layer.label}
        </button>
      ))}
    </div>
  );
}
