const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export interface Gym {
  gym_id: string;
  name: string;
  address: string;
  lat: number;
  lng: number;
  status: string;
  monthly_members: number;
  monthly_checkins: number;
  rating?: number;
  review_count?: number;
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

export interface Competitor {
  name: string;
  lat: number;
  lng: number;
  rating?: number;
}

export interface CensusTract {
  lat: number;
  lng: number;
  population: number;
  pct_age_18_34: number;
  median_income: number;
}

export interface GymAnalysis {
  gym_id: string;
  open_date: string;
  performance_tier: "Top Performer" | "Average" | "Underperforming";
  performance_rank_pct: number;
  trade_area: {
    population: number;
    median_income: number;
    median_age: number;
  };
  nearby_eos: Array<{
    gym_id: string;
    name: string;
    distance_miles: number;
  }>;
  nearby_competitors: Array<{
    name: string;
    lat: number;
    lng: number;
    rating?: number;
    distance_miles: number;
  }>;
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

export async function fetchGymAnalysis(gymId: string): Promise<GymAnalysis> {
  const res = await fetch(`${API_BASE}/api/gyms/${gymId}/analysis`);
  if (!res.ok) throw new Error("Failed to fetch gym analysis");
  return res.json() as Promise<GymAnalysis>;
}

export async function fetchCompetitors(lat: number, lng: number, radiusMiles = 10): Promise<Competitor[]> {
  const res = await fetch(`${API_BASE}/api/competitors?lat=${lat}&lng=${lng}&radius_miles=${radiusMiles}`);
  if (!res.ok) throw new Error("Failed to fetch competitors");
  const data = await res.json();
  return data.competitors as Competitor[];
}

export async function fetchCensusDensity(): Promise<CensusTract[]> {
  const res = await fetch(`${API_BASE}/api/census-density`);
  if (!res.ok) throw new Error("Census data not available");
  const data = await res.json();
  return data.tracts as CensusTract[];
}
