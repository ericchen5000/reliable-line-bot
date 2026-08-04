import json
import os

FAQ_FILE = "data/faq.json"


def load_faq():
    if not os.path.exists(FAQ_FILE):
        return []
    with open(FAQ_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def match_faq(question: str):
    faq = load_faq()

    q = question.lower()

    for item in faq:
        if item["question"].lower() in q:
            return item["answer"]

    return None
