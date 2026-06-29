from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
import json
import os

router = APIRouter()

LOG_PATH = "logs/chat_logs.json"


def load_logs():
    if not os.path.exists(LOG_PATH):
        return []

    with open(LOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@router.get("/logs")
def get_logs(
    limit: int = 50,
    offset: int = 0,
    user: str = None,
    keyword: str = None,
    sort: str = "desc"
):

    logs = load_logs()

    if user:
        logs = [l for l in logs if l.get("user") == user]

    if keyword:
        logs = [
            l for l in logs
            if keyword in l.get("message", "") or keyword in l.get("reply", "")
        ]

    logs.sort(key=lambda x: x.get("time", ""), reverse=(sort == "desc"))

    total = len(logs)
    logs = logs[offset:offset + limit]

    return JSONResponse({
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": logs
    })