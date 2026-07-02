from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from linebot import LineBotApi, WebhookHandler
from linebot.models import TextSendMessage
import asyncio
import json
import os
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from config import (
    LINE_CHANNEL_ACCESS_TOKEN,
    LINE_CHANNEL_SECRET,
    FAQ_FILE,
    SYSTEM_PROMPT_FILE,
)

from deepseek import ask_deepseek

app = FastAPI(title="AI Assistant")

from logs import router as logs_router
from faq import router as faq_router
from site_index import router as site_index_router
from dashboard import router as dashboard_router
from insights import router as insights_router
from services.search_index import build_all_indexes

app.include_router(dashboard_router)
app.include_router(logs_router)
app.include_router(faq_router)
app.include_router(site_index_router)
app.include_router(insights_router)

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

LOG_PATH = "logs/chat_logs.json"
URLS_FILE = "data/urls.json"
SITE_INDEX_INTERVAL_HOURS = int(os.getenv("SITE_INDEX_INTERVAL_HOURS", "24"))


async def site_index_scheduler():
    while True:
        await asyncio.sleep(SITE_INDEX_INTERVAL_HOURS * 60 * 60)
        await asyncio.to_thread(build_all_indexes)


@app.on_event("startup")
async def start_site_index_scheduler():
    asyncio.create_task(site_index_scheduler())


# =========================
# SYSTEM PROMPT
# =========================
def load_system_prompt():
    if SYSTEM_PROMPT_FILE and os.path.exists(SYSTEM_PROMPT_FILE):
        with open(SYSTEM_PROMPT_FILE, "r", encoding="utf-8") as f:
            return f.read()
    return ""

SYSTEM_PROMPT = load_system_prompt()


# =========================
# PLATFORM DETECT
# =========================
def detect_platform(request: Request):
    ua = request.headers.get("user-agent", "").lower()

    if "line" in ua:
        return "LINE"
    if "facebook" in ua or "fb" in ua:
        return "FB"
    return "WEB"


# =========================
# DEVICE DETECT
# =========================
def detect_device(request: Request):
    ua = request.headers.get("user-agent", "").lower()

    if any(x in ua for x in ["iphone", "android", "mobile"]):
        return "mobile"
    return "desktop"


# =========================
# BROWSER DETECT
# =========================
def detect_browser(request: Request):
    ua = request.headers.get("user-agent", "").lower()

    if "chrome" in ua:
        return "chrome"
    if "firefox" in ua:
        return "firefox"
    if "safari" in ua and "chrome" not in ua:
        return "safari"
    if "line" in ua:
        return "line-app"
    return "unknown"


# =========================
# FAQ
# =========================
def search_faq(question):
    if not FAQ_FILE or not os.path.exists(FAQ_FILE):
        return None, None

    try:
        with open(FAQ_FILE, "r", encoding="utf-8") as f:
            faq = json.load(f)
    except:
        return None, None

    q = question.strip().lower()

    for item in faq:
        faq_q = item.get("question", "").strip().lower()
        faq_a = item.get("answer", "")

        if faq_q == q or faq_q in q or q in faq_q:
            return faq_a, "FAQ"

    return None, None


# =========================
# SITEMAP
# =========================
def normalize_site_base(url):
    parsed = urlparse(url)

    if not parsed.scheme or not parsed.netloc:
        return None

    return f"{parsed.scheme}://{parsed.netloc}"


def fetch_sitemap_urls(site_base):
    sitemap_url = urljoin(site_base, "/sitemap.xml")

    try:
        r = requests.get(sitemap_url, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "xml")

        urls = [loc.text.strip() for loc in soup.find_all("loc") if loc.text]
        return urls[:80]

    except:
        return []


# =========================
# FETCH PAGE
# =========================
def fetch_url_content(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=8)
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "html.parser")

        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        text = soup.get_text(separator=" ")
        return " ".join(text.split())[:5000]

    except:
        return ""


# =========================
# URL CONFIG
# =========================
def search_urls(user_message):
    if not os.path.exists(URLS_FILE):
        return None

    try:
        with open(URLS_FILE, "r", encoding="utf-8") as f:
            urls = json.load(f)
    except:
        return None

    msg = user_message.lower()

    for item in urls:
        keywords = item.get("keywords", [])
        url = item.get("url", "")

        if url and any(k.lower() in msg for k in keywords):
            return item

    return None


def search_website_content(user_message, site):
    url = site.get("url", "")
    title = site.get("title") or url
    site_base = normalize_site_base(url)

    if not site_base:
        return None, None

    pages = fetch_sitemap_urls(site_base)

    if url not in pages:
        pages.insert(0, url)

    keywords = [
        word.strip().lower()
        for word in user_message.split()
        if word.strip()
    ]

    scored_pages = []

    for page in pages:
        page_base = normalize_site_base(page)

        if page_base != site_base:
            continue

        content = fetch_url_content(page)

        if not content or len(content) < 80:
            continue

        content_lower = content.lower()
        page_lower = page.lower()
        score = 0

        for keyword in keywords:
            if keyword in content_lower:
                score += 3
            if keyword in page_lower:
                score += 5

        if "/pr/" in page_lower:
            score += 3
        if "/news/" in page_lower:
            score += 2
        if "/product/" in page_lower:
            score += 2

        if score > 0:
            scored_pages.append((score, page, content))

    scored_pages.sort(key=lambda x: x[0], reverse=True)

    top_content = "\n\n".join(
        f"頁面：{page}\n內容：{content}"
        for _, page, content in scored_pages[:3]
    )

    if not top_content:
        top_content = fetch_url_content(url)

    if not top_content:
        return None, None

    prompt = SYSTEM_PROMPT + f"""

網站名稱：
{title}

網站來源：
{site_base}

網站內容：
{top_content}

請只根據以上網站內容回答使用者問題。
如果網站內容沒有答案，請回答「目前網站內容沒有相關資訊」。
"""

    answer = ask_deepseek(prompt, user_message)
    return answer, site_base


# =========================
# COMPANY
# =========================
def handle_company(user_message):
    keywords = ["公司", "電話", "地址", "email", "聯絡", "聯絡方式"]

    msg = user_message.lower()

    if any(k in msg for k in keywords):
        path = "data/company.json"
        if not os.path.exists(path):
            return None, None

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        return (
            "公司名稱：" + data.get("company_name", "") + "\n" +
            "電話：" + data.get("phone", "") + "\n" +
            "Email：" + data.get("email", "") + "\n" +
            "地址：" + data.get("address", "") + "\n" +
            "網站：" + data.get("website", "")
        ), "COMPANY"

    return None, None


# =========================
# KB
# =========================
def search_knowledge(user_message):
    kb_path = "knowledge"

    if not os.path.exists(kb_path):
        return None, None

    msg = user_message.lower()
    results = []

    for root, dirs, files in os.walk(kb_path):
        for file in files:
            if file.endswith(".txt"):
                path = os.path.join(root, file)

                with open(path, "r", encoding="utf-8") as f:
                    content = f.read().lower()

                    if msg in content:
                        results.append((content[:800], file))

    if results:
        text = "\n\n---\n\n".join([r[0] for r in results[:2]])
        names = [os.path.splitext(r[1])[0] for r in results[:2]]
        source = "KB-" + ",".join(names)
        return text, source

    return None, None


# =========================
# AI fallback
# =========================
def ai_fallback(user_message, context=""):
    prompt = SYSTEM_PROMPT + f"""

網站內容：
{context}

請根據內容回答（不可亂編）
"""

    return ask_deepseek(prompt, user_message), "AI"


# =========================
# ROUTER (FINAL STABLE VERSION)
# =========================
def ai_reply(user_message):

    faq, _ = search_faq(user_message)
    if faq:
        return faq, "FAQ"

    url_data = search_urls(user_message)

    if url_data:
        answer, source = search_website_content(user_message, url_data)
        if answer:
            return answer, source

    kb, src = search_knowledge(user_message)
    if kb:
        return kb, src

    company, _ = handle_company(user_message)
    if company:
        return company, "COMPANY"

    reply, _ = ai_fallback(user_message)
    return reply, "AI客服"


def admin_nav(active=""):
    items = [
        ("/", "Dashboard"),
        ("/logs", "LOGS"),
        ("/faq", "FAQ"),
        ("/site-index", "網站索引"),
        ("/unanswered", "未回答"),
        ("/faq-suggestions", "建議 FAQ"),
        ("/test-chat", "測試"),
        ("/health", "健康檢查"),
    ]
    return "".join(
        f'<a class="nav-link {"active" if active == label else ""}" href="{href}">{label}</a>'
        for href, label in items
    )


def admin_css():
    return """
    :root { --bg:#f6f7fb; --panel:#fff; --panel-soft:#f1f5f9; --text:#172033; --muted:#64748b; --border:#e2e8f0; --button-bg:linear-gradient(135deg,#60a5fa,#a78bfa); --danger:#dc2626; --shadow:0 16px 40px rgba(15,23,42,0.08); }
    * { box-sizing:border-box; }
    body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC"; background:radial-gradient(circle at top left, rgba(96,165,250,0.14), transparent 30%), var(--bg); color:var(--text); padding:24px; }
    .page { max-width:960px; margin:0 auto; }
    h2 { margin:0; font-size:28px; }
    .subtitle { color:var(--muted); font-size:13px; margin:8px 0 0; }
    .nav { display:flex; gap:8px; flex-wrap:wrap; margin:18px 0; }
    .nav-link { min-height:36px; padding:8px 12px; border-radius:8px; background:var(--panel); border:1px solid var(--border); color:var(--text); text-decoration:none; font-size:13px; font-weight:700; }
    .nav-link.active { color:white; background:var(--button-bg); border:none; }
    .card { background:var(--panel); border:1px solid var(--border); border-radius:8px; box-shadow:var(--shadow); padding:16px; margin-bottom:14px; }
    textarea, input { width:100%; padding:10px 12px; border:1px solid var(--border); border-radius:8px; background:var(--panel-soft); color:var(--text); margin-bottom:10px; }
    textarea { min-height:120px; resize:vertical; }
    button { min-height:40px; padding:8px 14px; border:none; border-radius:8px; color:white; background:var(--button-bg); font-weight:700; cursor:pointer; }
    table { width:100%; border-collapse:collapse; }
    td, th { padding:12px; border-top:1px solid var(--border); text-align:left; }
    th { background:var(--panel-soft); color:var(--muted); }
    .ok { color:#16a34a; font-weight:800; }
    .bad { color:var(--danger); font-weight:800; }
    @media (max-width:860px) { body { padding:14px; } h2 { font-size:24px; } }
    """


@app.get("/test-chat", response_class=HTMLResponse)
def test_chat_page(message: str = ""):
    answer = ""
    source = ""

    if message:
        answer, source = ai_reply(message)

    result_html = ""
    if answer:
        result_html = f"""
        <div class="card">
            <h3>測試結果</h3>
            <p><b>資料來源：</b>{html_escape(source)}</p>
            <div style="white-space:pre-wrap; line-height:1.7;">{html_escape(answer)}</div>
        </div>
        """

    return HTMLResponse(f"""
    <html><head><meta charset="utf-8"/><style>{admin_css()}</style></head>
    <body><main class="page">
    <h2>LINE 問答測試</h2><p class="subtitle">不用打開 LINE，直接測目前 AI 客服回答流程</p>
    <nav class="nav">{admin_nav("測試")}</nav>
    <form class="card" method="get" action="/test-chat">
        <textarea name="message" placeholder="輸入測試問題">{html_escape(message)}</textarea>
        <button>送出測試</button>
    </form>
    {result_html}
    </main></body></html>
    """)


def html_escape(value):
    import html
    return html.escape(str(value))


@app.get("/health", response_class=HTMLResponse)
def health_page():
    checks = [
        ("LINE_CHANNEL_ACCESS_TOKEN", bool(LINE_CHANNEL_ACCESS_TOKEN)),
        ("LINE_CHANNEL_SECRET", bool(LINE_CHANNEL_SECRET)),
        ("DEEPSEEK_API_KEY", bool(os.getenv("DEEPSEEK_API_KEY"))),
        ("FAQ 檔案", os.path.exists("data/faq.json")),
        ("URLS 檔案", os.path.exists("data/urls.json")),
        ("LOGS 目錄", os.path.exists("logs")),
        ("網站索引檔案", os.path.exists("data/site_index.json")),
    ]
    rows = "".join(
        f"<tr><td>{html_escape(name)}</td><td class='{'ok' if ok else 'bad'}'>{'OK' if ok else '缺少'}</td></tr>"
        for name, ok in checks
    )
    return HTMLResponse(f"""
    <html><head><meta charset="utf-8"/><style>{admin_css()}</style></head>
    <body><main class="page">
    <h2>健康檢查</h2><p class="subtitle">確認服務設定與必要資料檔是否存在</p>
    <nav class="nav">{admin_nav("健康檢查")}</nav>
    <div class="card"><table><tr><th>項目</th><th>狀態</th></tr>{rows}</table></div>
    </main></body></html>
    """)


# =========================
# LOG SAVE
# =========================
def save_log(user, message, reply, request: Request, platform, latency, source):

    os.makedirs("logs", exist_ok=True)

    if not os.path.exists(LOG_PATH):
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            json.dump([], f)

    try:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            logs = json.load(f)
    except:
        logs = []

    ip = request.headers.get("x-forwarded-for") or request.client.host or "-"

    logs.append({
        "id": len(logs) + 1,
        "time": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
        "user": user,
        "message": message,
        "reply": reply,
        "platform": platform,
        "latency": latency,
        "ip": ip,
        "source": source
    })

    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)


# =========================
# LINE WEBHOOK
# =========================
@app.post("/line/webhook")
async def line_webhook(request: Request):

    start = time.time()
    body = await request.json()

    if "events" not in body:
        raise HTTPException(status_code=400)

    for event in body["events"]:

        if event.get("type") != "message":
            continue

        if event["message"]["type"] != "text":
            continue

        user_msg = event["message"]["text"]
        user_id = event["source"].get("userId")

        platform = detect_platform(request)

        reply, source = ai_reply(user_msg)

        latency = round(time.time() - start, 3)

        final_reply = f"{reply}\n\n資料來源：{source}"

        line_bot_api.reply_message(
            event["replyToken"],
            TextSendMessage(text=final_reply[:1000])
        )

        save_log(
            user_id,
            user_msg,
            reply,
            request,
            platform,
            latency,
            source
        )

    return {"status": "ok"}
