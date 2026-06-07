export type { Gym, NearbyGym, ScoreResult } from "@/lib/api";

export type LayerId = "gym-locations" | "member-density" | "drive-time" | "drive-time-25" | "competitors";

export interface Layer {
  id: LayerId;
  label: string;
  active: boolean;
}
