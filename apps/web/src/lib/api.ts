const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface Gym {
  gym_id: string;
  name: string;
  lat: number;
  lng: number;
  status: string;
  monthly_members: number;
  monthly_checkins: number;
}

export interface NearbyGym {
  gym_id: string;
  name: string;
  lat: number;
  lng: number;
  distance_miles: number;
}

export interface ScoreResult {
  lat: number;
  lng: number;
  opportunity_score: number;
  projected_checkins: number;
  cannibalization_risk: number;
  net_network_impact: number;
  nearby_gyms: NearbyGym[];
}

export async function fetchGyms(): Promise<Gym[]> {
  const res = await fetch(`${API_BASE}/api/gyms`);
  if (!res.ok) throw new Error("Failed to fetch gyms");
  const data = await res.json();
  return data.gyms as Gym[];
}

export async function scoreLocation(lat: number, lng: number): Promise<ScoreResult> {
  const res = await fetch(`${API_BASE}/api/score-location`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ lat, lng }),
  });
  if (!res.ok) throw new Error("Failed to score location");
  return res.json() as Promise<ScoreResult>;
}
