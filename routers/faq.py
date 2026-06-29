from fastapi import APIRouter
import json
import os

router = APIRouter()

FAQ_FILE = "data/faq.json"


def load_faq():
    if not os.path.exists(FAQ_FILE):
        return []
    with open(FAQ_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_faq(data):
    os.makedirs("data", exist_ok=True)
    with open(FAQ_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


@router.get("/faq")
def get_faq():
    return load_faq()


@router.post("/faq")
def add_faq(item: dict):
    data = load_faq()
    data.append(item)
    save_faq(data)
    return {"status": "ok", "count": len(data)}


@router.delete("/faq")
def delete_faq(index: int):
    data = load_faq()
    if 0 <= index < len(data):
        data.pop(index)
        save_faq(data)
    return {"status": "ok", "count": len(data)}
