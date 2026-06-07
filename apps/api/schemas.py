from pydantic import BaseModel


class ScoreRequest(BaseModel):
    lat: float
    lng: float
