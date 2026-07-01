# search_index.py

import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
import json
import os

HEADERS = {"User-Agent": "Mozilla/5.0"}

INDEX_FILE = "data/site_index.json"


# =========================
# sitemap loader
# =========================
def get_sitemap_urls(domain: str):
    sitemap = f"{domain}/sitemap.xml"

    try:
        r = requests.get(sitemap, timeout=10)
        soup = BeautifulSoup(r.text, "xml")

        urls = [loc.text for loc in soup.find_all("loc")]
        return urls

    except:
        return []


# =========================
# fetch page text
# =========================
def fetch_page(url: str):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        for t in soup(["script", "style", "noscript"]):
            t.decompose()

        text = soup.get_text(" ")
        text = " ".join(text.split())

        return text

    except:
        return ""


# =========================
# chunk text
# =========================
def chunk_text(text, size=800):
    words = text.split()
    chunks = []

    for i in range(0, len(words), size):
        chunks.append(" ".join(words[i:i+size]))

    return chunks


# =========================
# build index
# =========================
def build_index(domain="https://www.reliable.com.tw"):
    urls = get_sitemap_urls(domain)

    index = []

    for url in urls:
        content = fetch_page(url)

        if not content:
            continue

        chunks = chunk_text(content)

        for c in chunks:
            index.append({
                "url": url,
                "text": c
            })

    os.makedirs("data", exist_ok=True)

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=2)

    return len(index)