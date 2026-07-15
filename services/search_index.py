# search_index.py

import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import json
import os
from datetime import datetime
import re

HEADERS = {"User-Agent": "Mozilla/5.0"}

INDEX_FILE = "data/site_index.json"
URLS_FILE = "data/urls.json"
STATUS_FILE = "data/site_index_status.json"
MAX_PAGES_PER_SITE = int(os.getenv("SITE_INDEX_MAX_PAGES_PER_SITE", "120"))
MAX_LINK_DEPTH = int(os.getenv("SITE_INDEX_MAX_LINK_DEPTH", "2"))
MIN_TEXT_LENGTH = 80


def site_base(url):
    parsed = urlparse(url)

    if not parsed.scheme or not parsed.netloc:
        return None

    return f"{parsed.scheme}://{parsed.netloc}"


def normalize_url(url):
    parsed = urlparse(url)

    if not parsed.scheme or not parsed.netloc:
        return ""

    path = parsed.path or "/"
    normalized = parsed._replace(fragment="", query="", path=path)
    return normalized.geturl().rstrip("/") + ("/" if path.endswith("/") else "")


def path_prefix(url):
    parsed = urlparse(url)
    path = parsed.path or "/"

    if path == "/":
        return "/"

    if path.endswith("/"):
        return path

    return path.rsplit("/", 1)[0] + "/"


def is_allowed_url(url, base, seed_url):
    if site_base(url) != base:
        return False

    parsed = urlparse(url)
    path = parsed.path or "/"

    if any(skip in path.lower() for skip in ["/wp-admin", "/wp-login", "/feed", "/tag/"]):
        return False

    if re.search(r"\.(jpg|jpeg|png|gif|webp|svg|pdf|zip|rar|7z|mp4|mov|avi)$", path.lower()):
        return False

    seed_prefix = path_prefix(seed_url)

    if seed_prefix == "/":
        return True

    return path.startswith(seed_prefix) or path.startswith("/pr/") or path.startswith("/kb/")


def load_sites():
    if not os.path.exists(URLS_FILE):
        return [{"title": "Reliable Information 官方網站", "url": "https://www.reliable.com.tw/"}]

    try:
        with open(URLS_FILE, "r", encoding="utf-8") as f:
            sites = json.load(f)
    except:
        return []

    return [site for site in sites if site.get("url") and site.get("active", True) is not False]


# =========================
# sitemap loader
# =========================
def get_sitemap_urls(domain: str):
    sitemap = urljoin(domain, "/sitemap.xml")

    try:
        r = requests.get(sitemap, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "xml")

        urls = [normalize_url(loc.text.strip()) for loc in soup.find_all("loc") if loc.text]
        return [url for url in urls if url]

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
        title = soup.title.get_text(" ", strip=True) if soup.title else ""

        for t in soup(["script", "style", "noscript"]):
            t.decompose()

        text = soup.get_text(" ")
        text = " ".join(text.split())

        return title, text

    except:
        return "", ""


def fetch_links(url, base, seed_url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
    except:
        return []

    links = []

    for tag in soup.find_all("a", href=True):
        absolute = normalize_url(urljoin(url, tag["href"]))

        if absolute and is_allowed_url(absolute, base, seed_url):
            links.append(absolute)

    return links


# =========================
# chunk text
# =========================
def chunk_text(text, size=700):
    words = text.split()
    chunks = []

    if len(words) <= size:
        return [text]

    for i in range(0, len(words), size):
        chunks.append(" ".join(words[i:i+size]))

    return chunks


def discover_urls(seed_url):
    base = site_base(seed_url)

    if not base:
        return []

    seed_url = normalize_url(seed_url)
    sitemap_urls = [
        url for url in get_sitemap_urls(base)
        if is_allowed_url(url, base, seed_url)
    ]
    queue = [(seed_url, 0)]
    seen = set()
    discovered = []

    for url in sitemap_urls:
        if url not in seen:
            queue.append((url, 1))

    while queue and len(discovered) < MAX_PAGES_PER_SITE:
        url, depth = queue.pop(0)

        if url in seen:
            continue

        seen.add(url)
        discovered.append(url)

        if depth >= MAX_LINK_DEPTH:
            continue

        for link in fetch_links(url, base, seed_url):
            if link not in seen and len(queue) < MAX_PAGES_PER_SITE * 2:
                queue.append((link, depth + 1))

    return discovered[:MAX_PAGES_PER_SITE]


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
        return [], {"pages": 0, "chunks": 0, "failed": 0}

    urls = discover_urls(domain)
    index = []
    failed = 0

    for url in urls:
        if site_base(url) != base:
            continue

        page_title, content = fetch_page(url)

        if not content or len(content) < MIN_TEXT_LENGTH:
            failed += 1
            continue

        chunks = chunk_text(content)

        for c in chunks:
            index.append({
                "site": title,
                "site_base": base,
                "url": url,
                "title": page_title or title,
                "text": c
            })

    return index, {
        "pages": len(urls),
        "chunks": len(index),
        "failed": failed
    }


def build_all_indexes():
    all_index = []
    site_results = []
    seen_chunks = set()

    for site in load_sites():
        title = site.get("title") or site.get("url")
        url = site.get("url")
        site_index, result = build_index(url, title)

        for item in site_index:
            key = (item.get("url"), item.get("text", "")[:120])

            if key in seen_chunks:
                continue

            seen_chunks.add(key)
            all_index.append(item)

        site_results.append({
            "title": title,
            "url": url,
            "pages": result.get("pages", 0),
            "chunks": len(site_index),
            "failed": result.get("failed", 0)
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
