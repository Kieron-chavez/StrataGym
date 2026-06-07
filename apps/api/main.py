from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import gyms, scoring, competitors, census

app = FastAPI(title="StrataGym API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(gyms.router)
app.include_router(scoring.router)
app.include_router(competitors.router)
app.include_router(census.router)
