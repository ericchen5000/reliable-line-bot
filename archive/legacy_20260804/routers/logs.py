from fastapi import APIRouter
from core.db import get_logs

router = APIRouter()

@router.get("/logs")
def logs(limit: int = 50):
    return get_logs(limit)
