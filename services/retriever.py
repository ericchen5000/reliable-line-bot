# retriever.py

import json

INDEX_FILE = "data/site_index.json"
STOP_WORDS = {
    "的", "是", "有", "和", "或", "嗎", "什麼", "目前", "關於",
    "請問", "一下", "資訊", "資料", "知識庫", "ai", "the", "is",
    "a", "an", "of", "and", "or", "to", "in", "on", "for"
}


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
    q_words = [
        word.strip(" ?!,.，。？！、：:")
        for word in q.split()
    ]
    q_words = [
        word for word in q_words
        if len(word) >= 2 and word not in STOP_WORDS
    ]
    t = text.lower()

    s = 0

    if q and q in t:
        s += 8

    for w in q_words:
        if w in t:
            s += 2

    return s


def minimum_score(query):
    words = [
        word.strip(" ?!,.，。？！、：:")
        for word in query.lower().split()
    ]
    words = [
        word for word in words
        if len(word) >= 2 and word not in STOP_WORDS
    ]

    if len(words) <= 1:
        return 4

    return 6


# =========================
# retrieve top-k pages
# =========================
def retrieve(query, top_k=3):
    data = load_index()
    min_score = minimum_score(query)

    scored = []

    for item in data:
        text = item.get("text", "")
        if not text:
            continue

        s = score(text, query)

        if s >= min_score:
            item = dict(item)
            item["_score"] = s
            scored.append((s, item))

    scored.sort(key=lambda x: x[0], reverse=True)

    return [x[1] for x in scored[:top_k]]
