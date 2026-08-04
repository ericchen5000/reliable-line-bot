import json
import os
import re


BRAND_DICTIONARY_FILE = "data/brand_dictionary.json"

STOPWORDS = {
    "什麼", "哪些", "那些", "有什麼", "介紹", "說明", "比較", "產品",
    "請問", "可以", "一下", "我們", "你們", "的是", "資訊", "資料",
    "the", "and", "with", "for", "about",
}


def load_brand_dictionary():
    if not os.path.exists(BRAND_DICTIONARY_FILE):
        return []

    try:
        with open(BRAND_DICTIONARY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except Exception:
        return []


def matched_brand_entries(message):
    text = str(message or "").lower()
    if not text:
        return []

    ascii_tokens = set(re.findall(r"[a-z0-9][a-z0-9.+-]*", text))

    def candidate_matches(candidate):
        value = str(candidate or "").lower().strip()
        if not value:
            return False
        if re.fullmatch(r"[a-z0-9.+-]+", value) and len(value) <= 3:
            return value in ascii_tokens
        return value in text

    matches = []
    for item in load_brand_dictionary():
        if item.get("active", True) is False:
            continue

        aliases = item.get("aliases") or []
        products = item.get("products") or []
        candidates = [item.get("brand", ""), item.get("display_name", ""), *aliases, *products]

        if any(candidate_matches(candidate) for candidate in candidates):
            matches.append(item)

    return matches


def expand_query(message):
    text = str(message or "")
    additions = []

    for item in matched_brand_entries(text):
        values = [
            item.get("brand", ""),
            item.get("display_name", ""),
            *(item.get("aliases") or []),
            *(item.get("products") or []),
            *(item.get("keywords") or []),
            *(item.get("urls") or []),
        ]
        additions.extend(str(value).strip() for value in values if str(value or "").strip())

    if not additions:
        return text

    unique = list(dict.fromkeys(additions))
    return text + " " + " ".join(unique)


def search_terms(message):
    text = expand_query(message).lower()
    terms = re.findall(r"[a-z0-9][a-z0-9.+-]*|[\u4e00-\u9fff]{2,}", text)
    cleaned = []

    for term in terms:
        if term in STOPWORDS:
            continue
        if term not in cleaned:
            cleaned.append(term)

    return cleaned


def is_specific_brand_or_product_question(message):
    return bool(matched_brand_entries(message))
