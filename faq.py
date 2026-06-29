from fastapi import APIRouter
import json
import os

router = APIRouter()

FAQ_FILE = "data/faq.json"


@router.get("/faq")
def get_faq():

    if not os.path.exists(FAQ_FILE):
        return {"data": []}

    with open(FAQ_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    return {"data": data}