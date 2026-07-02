# retriever.py

import json

INDEX_FILE = "data/site_index.json"


# =========================
# load index
# =========================
def load_index():
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except:
        return []


# =========================
# simple scoring
# =========================
def score(text, query):
    q = query.lower().strip()
    q_words = q.split()
    t = text.lower()

    s = 0

    if q and q in t:
        s += 8

    for w in q_words:
        if w in t:
            s += 2

    return s


# =========================
# retrieve top-k pages
# =========================
def retrieve(query, top_k=3):
    data = load_index()

    scored = []

    for item in data:
        text = item.get("text", "")
        if not text:
            continue

        s = score(text, query)

        if s > 0:
            scored.append((s, item))

    scored.sort(key=lambda x: x[0], reverse=True)

    return [x[1] for x in scored[:top_k]]
