# search_index.py

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import json
import os
from datetime import datetime

HEADERS = {"User-Agent": "Mozilla/5.0"}

INDEX_FILE = "data/site_index.json"
URLS_FILE = "data/urls.json"
STATUS_FILE = "data/site_index_status.json"


def site_base(url):
    parsed = urlparse(url)

    if not parsed.scheme or not parsed.netloc:
        return None

    return f"{parsed.scheme}://{parsed.netloc}"


def load_sites():
    if not os.path.exists(URLS_FILE):
        return [{"title": "Reliable Information 官方網站", "url": "https://www.reliable.com.tw/"}]

    try:
        with open(URLS_FILE, "r", encoding="utf-8") as f:
            sites = json.load(f)
    except:
        return []

    return [site for site in sites if site.get("url")]


# =========================
# sitemap loader
# =========================
def get_sitemap_urls(domain: str):
    sitemap = urljoin(domain, "/sitemap.xml")

    try:
        r = requests.get(sitemap, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "xml")

        urls = [loc.text.strip() for loc in soup.find_all("loc") if loc.text]
        return urls

    except:
        return []


# =========================
# fetch page text
# =========================
def fetch_page(url: str):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
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
def save_status(status):
    os.makedirs("data", exist_ok=True)

    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)


def load_status():
    if not os.path.exists(STATUS_FILE):
        return {}

    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}


def build_index(domain="https://www.reliable.com.tw", title="Reliable Information 官方網站"):
    base = site_base(domain)

    if not base:
        return []

    urls = get_sitemap_urls(base)

    if domain not in urls:
        urls.insert(0, domain)

    index = []

    for url in urls:
        if site_base(url) != base:
            continue

        content = fetch_page(url)

        if not content:
            continue

        chunks = chunk_text(content)

        for c in chunks:
            index.append({
                "site": title,
                "site_base": base,
                "url": url,
                "text": c
            })

    return index


def build_all_indexes():
    all_index = []
    site_results = []

    for site in load_sites():
        title = site.get("title") or site.get("url")
        url = site.get("url")
        site_index = build_index(url, title)
        all_index.extend(site_index)
        site_results.append({
            "title": title,
            "url": url,
            "chunks": len(site_index)
        })

    os.makedirs("data", exist_ok=True)

    with open(INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(all_index, f, ensure_ascii=False, indent=2)

    status = {
        "last_run": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
        "total_chunks": len(all_index),
        "sites": site_results
    }
    save_status(status)

    return status
