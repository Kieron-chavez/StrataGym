from __future__ import annotations

# Module-level cache shared across routers.
# competitors is populated by GET /api/competitors and read by GET /api/gyms/:id/analysis.
competitors: list[dict] | None = None

# census_tracts is populated lazily on first gym analysis request.
census_tracts: list[dict] | None = None
