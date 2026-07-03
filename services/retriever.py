# retriever.py

import json
import re

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


def tokenize(query):
    q = query.lower().strip()
    rough_tokens = [
        word.strip(" ?!,.，。？！、：:；;「」『』()（）[]【】")
        for word in re.split(r"\s+", q)
    ]
    tokens = [
        word for word in rough_tokens
        if len(word) >= 2 and word not in STOP_WORDS
    ]
    cjk_runs = re.findall(r"[\u4e00-\u9fff]{2,}", q)

    for run in cjk_runs:
        if run not in STOP_WORDS:
            tokens.append(run)

        for size in (2, 3, 4):
            for i in range(0, max(0, len(run) - size + 1)):
                piece = run[i:i + size]

                if piece not in STOP_WORDS:
                    tokens.append(piece)

    seen = set()
    unique = []

    for token in tokens:
        if token and token not in seen:
            seen.add(token)
            unique.append(token)

    return unique


# =========================
# weighted scoring
# =========================
def score(item, query):
    q = query.lower().strip()
    tokens = tokenize(query)
    title = str(item.get("title", "")).lower()
    url = str(item.get("url", "")).lower()
    text = str(item.get("text", "")).lower()
    haystack = f"{title}\n{url}\n{text}"

    s = 0

    if q and q in title:
        s += 30
    if q and q in text:
        s += 18
    if q and q in url:
        s += 12

    for token in tokens:
        if token in title:
            s += 8
        if token in url:
            s += 5
        if token in text:
            s += 2

    if any(path in url for path in ["/pr/", "/category/pr/"]):
        s += 2
    if any(path in url for path in ["/kb/", "/category/kb/"]):
        s += 2
    if "array" in q and "array" in haystack:
        s += 5
    if "shadow" in q and "shadow" in haystack:
        s += 5

    return s


def minimum_score(query):
    words = tokenize(query)

    if len(words) <= 1:
        return 12

    return 18


def has_meaningful_match(item, query):
    tokens = tokenize(query)
    title = str(item.get("title", "")).lower()
    url = str(item.get("url", "")).lower()
    text = str(item.get("text", "")).lower()
    q = query.lower().strip()

    if q and (q in title or q in text or q in url):
        return True

    meaningful_tokens = [
        token for token in tokens
        if token not in {"定承", "承資", "資訊", "reliable", "公司", "客服"}
    ]

    hits = 0

    for token in meaningful_tokens:
        if token in title or token in url or token in text:
            hits += 1

    return hits >= 2


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

        s = score(item, query)

        if s >= min_score and has_meaningful_match(item, query):
            item = dict(item)
            item["_score"] = s
            scored.append((s, item))

    scored.sort(key=lambda x: x[0], reverse=True)

    return [x[1] for x in scored[:top_k]]
