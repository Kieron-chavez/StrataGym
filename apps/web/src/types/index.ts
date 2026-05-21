export type { Gym, NearbyGym, ScoreResult } from "@/lib/api";

export type LayerId = "gym-locations" | "member-density" | "drive-time" | "competitors";

export interface Layer {
  id: LayerId;
  label: string;
  active: boolean;
}
