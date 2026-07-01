# retriever.py

import json
import math

INDEX_FILE = "data/site_index.json"


# =========================
# load index
# =========================
def load_index():
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


# =========================
# simple scoring
# =========================
def score(text, query):
    q_words = query.lower().split()
    t = text.lower()

    s = 0
    for w in q_words:
        if w in t:
            s += 1

    return s


# =========================
# retrieve top-k pages
# =========================
def retrieve(query, top_k=3):
    data = load_index()

    scored = []

    for item in data:
        s = score(item["text"], query)

        if s > 0:
            scored.append((s, item))

    scored.sort(key=lambda x: x[0], reverse=True)

    return [x[1] for x in scored[:top_k]]