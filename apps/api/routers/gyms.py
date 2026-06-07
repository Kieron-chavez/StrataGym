from fastapi import APIRouter
from store import GYMS

router = APIRouter()


@router.get("/api/gyms")
def get_gyms():
    return {"gyms": GYMS}
