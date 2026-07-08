from fastapi import FastAPI, Request, HTTPException, Form, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from linebot import LineBotApi, WebhookHandler
from linebot.models import TextSendMessage
import asyncio
import base64
import hashlib
import hmac
import json
import os
import secrets
import shutil
import subprocess
import tempfile
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

WEB_CHAT_ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "WEB_CHAT_ALLOWED_ORIGINS",
        "https://www.reliable.com.tw,https://reliable.com.tw,http://www.reliable.com.tw,http://reliable.com.tw"
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=WEB_CHAT_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["*"],
)

from logs import router as logs_router
from faq import router as faq_router
from site_index import router as site_index_router
from dashboard import router as dashboard_router
from insights import router as insights_router
from analytics import router as analytics_router
from services.search_index import build_all_indexes
from services.retriever import retrieve

app.include_router(dashboard_router)
app.include_router(logs_router)
app.include_router(faq_router)
app.include_router(site_index_router)
app.include_router(insights_router)
app.include_router(analytics_router)

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

LOG_PATH = "logs/chat_logs.json"
URLS_FILE = "data/urls.json"
SITE_INDEX_FILE = "data/site_index.json"
SITE_INDEX_INTERVAL_HOURS = int(os.getenv("SITE_INDEX_INTERVAL_HOURS", "24"))
ADMIN_USERS_PATH = "data/admin_users.json"
AUTH_COOKIE = "reliable_admin"
AUTH_MAX_AGE = 60 * 60 * 12
AUTH_SECRET = os.getenv("ADMIN_AUTH_SECRET") or LINE_CHANNEL_SECRET or secrets.token_hex(32)
IMAGE_UPLOAD_DIR = "logs/images"
VISION_API_URL = os.getenv("VISION_API_URL", "").strip()
VISION_API_KEY = os.getenv("VISION_API_KEY", "").strip()
VISION_MODEL = os.getenv("VISION_MODEL", "gpt-4o-mini").strip()


async def site_index_scheduler():
    while True:
        await asyncio.sleep(SITE_INDEX_INTERVAL_HOURS * 60 * 60)
        await asyncio.to_thread(build_all_indexes)


@app.on_event("startup")
async def start_site_index_scheduler():
    asyncio.create_task(site_index_scheduler())


# =========================
# ADMIN AUTH
# =========================
def load_admin_users():
    if not os.path.exists(ADMIN_USERS_PATH):
        return []

    try:
        with open(ADMIN_USERS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except:
        return []


def save_admin_users(users):
    os.makedirs(os.path.dirname(ADMIN_USERS_PATH), exist_ok=True)
    with open(ADMIN_USERS_PATH, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def hash_password(password, salt=None):
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        str(password).encode("utf-8"),
        salt.encode("utf-8"),
        120000
    ).hex()
    return f"pbkdf2_sha256${salt}${digest}"


def verify_password(password, stored):
    try:
        method, salt, digest = str(stored).split("$", 2)
    except ValueError:
        return False

    if method != "pbkdf2_sha256":
        return False

    expected = hash_password(password, salt).split("$", 2)[2]
    return hmac.compare_digest(expected, digest)


def sign_value(value):
    return hmac.new(
        AUTH_SECRET.encode("utf-8"),
        value.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def make_auth_token(username):
    expires = int(time.time()) + AUTH_MAX_AGE
    payload = f"{username}|{expires}"
    signature = sign_value(payload)
    token = f"{payload}|{signature}".encode("utf-8")
    return base64.urlsafe_b64encode(token).decode("utf-8")


def read_auth_token(token):
    if not token:
        return None

    try:
        decoded = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
        username, expires, signature = decoded.rsplit("|", 2)
    except:
        return None

    payload = f"{username}|{expires}"

    if not hmac.compare_digest(sign_value(payload), signature):
        return None

    try:
        if int(expires) < int(time.time()):
            return None
    except:
        return None

    users = load_admin_users()

    if not any(user.get("username") == username for user in users):
        return None

    return username


def current_admin(request: Request):
    return read_auth_token(request.cookies.get(AUTH_COOKIE))


def is_public_path(path):
    public_exact = {
        "/login",
        "/logout",
        "/chat",
        "/web/chat",
        "/web/image",
        "/web/lead",
        "/line/webhook",
    }
    public_prefixes = ()
    return path in public_exact or any(path.startswith(prefix) for prefix in public_prefixes)


@app.middleware("http")
async def admin_auth_middleware(request: Request, call_next):
    if request.method == "OPTIONS" or is_public_path(request.url.path):
        return await call_next(request)

    if current_admin(request):
        return await call_next(request)

    return RedirectResponse("/login", status_code=302)


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
# IMAGE RECOGNITION
# =========================
def image_ext(content_type="", filename=""):
    ext = os.path.splitext(str(filename or ""))[1].lower()

    if ext in {".jpg", ".jpeg", ".png", ".gif", ".webp"}:
        return ext

    if "png" in content_type:
        return ".png"
    if "webp" in content_type:
        return ".webp"
    if "gif" in content_type:
        return ".gif"

    return ".jpg"


def save_image_bytes(content, filename="", content_type=""):
    os.makedirs(IMAGE_UPLOAD_DIR, exist_ok=True)
    ext = image_ext(content_type, filename)
    name = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{secrets.token_hex(4)}{ext}"
    path = os.path.join(IMAGE_UPLOAD_DIR, name)

    with open(path, "wb") as f:
        f.write(content)

    return path


def run_tesseract_ocr(image_path):
    tesseract = shutil.which("tesseract")

    if not tesseract:
        return {
            "ok": False,
            "text": "",
            "detail": "目前尚未啟用圖片文字辨識功能，請稍後改用文字描述問題。"
        }

    languages = os.getenv("OCR_LANG", "chi_tra+eng")

    try:
        result = subprocess.run(
            [tesseract, image_path, "stdout", "-l", languages],
            capture_output=True,
            text=True,
            timeout=25
        )
    except Exception as exc:
        return {
            "ok": False,
            "text": "",
            "detail": f"圖片文字辨識暫時無法使用：{exc}"
        }

    if result.returncode != 0:
        error_text = (result.stderr or result.stdout or "").strip()
        return {
            "ok": False,
            "text": "",
            "detail": f"圖片文字辨識暫時無法使用：{error_text or '未知錯誤'}"
        }

    text = result.stdout.strip()

    if not text:
        return {
            "ok": False,
            "text": "",
            "detail": "沒有辨識出文字。可能圖片文字太小、太模糊，或圖片本身沒有文字。"
        }

    return {
        "ok": True,
        "text": text,
        "detail": f"tesseract OCR 成功，語言：{languages}"
    }


def call_vision_api(image_bytes, content_type="image/jpeg"):
    if not VISION_API_URL or not VISION_API_KEY:
        return ""

    encoded = base64.b64encode(image_bytes).decode("utf-8")
    data_url = f"data:{content_type or 'image/jpeg'};base64,{encoded}"
    headers = {
        "Authorization": f"Bearer {VISION_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": VISION_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "你是企業客服圖片辨識助手。請用繁體中文描述圖片內容，特別留意錯誤訊息、產品名稱、授權資訊、畫面文字與使用者可能需要的協助。"
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "請辨識這張圖片，整理成客服可用的文字描述。"},
                    {"type": "image_url", "image_url": {"url": data_url}},
                ]
            }
        ],
        "temperature": 0.2,
    }

    try:
        response = requests.post(VISION_API_URL, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()
    except:
        return ""


def analyze_image(content, filename="", content_type="image/jpeg"):
    image_path = save_image_bytes(content, filename, content_type)
    ocr_result = run_tesseract_ocr(image_path)
    ocr_text = ocr_result.get("text", "")
    vision_text = call_vision_api(content, content_type)
    parts = []
    notes = []

    if ocr_text:
        parts.append(f"圖片 OCR 文字：\n{ocr_text}")
    else:
        notes.append(ocr_result.get("detail", "OCR 未取得文字"))

    if vision_text:
        parts.append(f"圖片內容描述：\n{vision_text}")
    else:
        notes.append("目前尚未啟用圖片內容描述功能。")

    if not parts:
        return {
            "ok": False,
            "image_path": image_path,
            "text": "",
            "message": "已收到圖片，但目前沒有取得可用的圖片辨識結果。\n\n" + "\n".join(f"- {note}" for note in notes)
        }

    text = "\n\n".join(parts)
    return {
        "ok": True,
        "image_path": image_path,
        "text": text,
        "message": text
    }


def answer_image_question(image_text):
    question = f"使用者傳了一張圖片，圖片辨識結果如下：\n\n{image_text}\n\n請根據圖片內容，用客服口吻協助判斷使用者可能遇到的問題，並提供下一步建議。"
    reply, source = ai_reply(question)
    return reply, source, question


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
# SITE INDEX
# =========================
def search_site_index(user_message):
    pages = retrieve(user_message, top_k=3)

    if not pages:
        return None, None

    context = "\n\n".join(
        "網站：{site}\n標題：{title}\n頁面：{url}\n搜尋分數：{score}\n內容：{text}".format(
            site=page.get("site", page.get("site_base", "")),
            title=page.get("title", ""),
            url=page.get("url", ""),
            score=page.get("_score", ""),
            text=page.get("text", "")[:1600]
        )
        for page in pages
    )
    source_urls = []

    for page in pages:
        url = page.get("url") or page.get("site_base")

        if url and url not in source_urls:
            source_urls.append(url)

    prompt = SYSTEM_PROMPT + f"""

網站索引內容：
{context}

請只根據以上網站索引內容回答使用者問題。
如果索引內容沒有答案，請回答「目前網站索引沒有相關資訊」。
"""

    answer = ask_deepseek(prompt, user_message)

    no_answer_markers = [
        "目前網站索引沒有相關資訊",
        "網站索引沒有相關資訊",
        "沒有相關資訊",
        "索引內容沒有答案",
    ]

    if any(marker in answer for marker in no_answer_markers):
        return None, None

    return answer, "網站索引 - " + ",".join(source_urls[:3])


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

    company, _ = handle_company(user_message)
    if company:
        return company, "COMPANY"

    kb, src = search_knowledge(user_message)
    if kb:
        return kb, src

    indexed_answer, indexed_source = search_site_index(user_message)
    if indexed_answer:
        return indexed_answer, indexed_source

    url_data = search_urls(user_message)

    if url_data:
        answer, source = search_website_content(user_message, url_data)
        if answer:
            return answer, source

    reply, _ = ai_fallback(user_message)
    return reply, "AI客服"


def admin_nav(active=""):
    items = [
        ("/", "Dashboard"),
        ("/logs", "LOGS"),
        ("/faq", "知識管理"),
        ("/test-chat", "測試"),
        ("/admin/users", "帳號管理"),
    ]
    links = "".join(
        f'<a class="nav-link {"active" if active == label else ""}" href="{href}">{label}</a>'
        for href, label in items
    )
    return f'<button type="button" class="nav-toggle" onclick="this.closest(\'nav\').classList.toggle(\'open\')">☰ 選單</button><div class="nav-menu">{links}</div>'


def admin_css():
    return """
    :root { --bg:#f6f7fb; --panel:#fff; --panel-soft:#f1f5f9; --text:#172033; --muted:#64748b; --border:#e2e8f0; --button-bg:linear-gradient(135deg,#60a5fa,#a78bfa); --danger:#dc2626; --shadow:0 16px 40px rgba(15,23,42,0.08); }
    * { box-sizing:border-box; }
    body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC"; background:radial-gradient(circle at top left, rgba(96,165,250,0.14), transparent 30%), var(--bg); min-height:100vh; color:var(--text); padding:24px; font-size:16px; }
    body.dark { --bg:#0f172a; --panel:#162033; --panel-soft:#1e293b; --text:#e5edf7; --muted:#94a3b8; --border:#334155; --shadow:0 16px 40px rgba(0,0,0,0.28); }
    .page { max-width:1280px; margin:0 auto; }
    .topbar { display:flex; justify-content:space-between; align-items:flex-end; gap:16px; margin-bottom:18px; }
    h2 { margin:0; font-size:28px; }
    .subtitle { color:var(--muted); font-size:13px; margin:8px 0 0; }
    .theme-control { flex:0 0 auto; display:flex; align-items:center; gap:10px; padding:8px 10px 8px 14px; border-radius:999px; border:1px solid var(--border); background:var(--panel); box-shadow:var(--shadow); color:var(--muted); font-size:13px; font-weight:700; cursor:pointer; user-select:none; }
    .switch { position:relative; width:52px; height:30px; flex:0 0 auto; }
    .switch input { position:absolute; opacity:0; width:0; height:0; }
    .slider { position:absolute; inset:0; border-radius:999px; background:#cbd5e1; transition:background 0.2s ease; box-shadow:inset 0 1px 3px rgba(15,23,42,0.18); }
    .slider::before { content:""; position:absolute; width:26px; height:26px; left:2px; top:2px; border-radius:50%; background:#fff; box-shadow:0 2px 8px rgba(15,23,42,0.25); transition:transform 0.2s ease; }
    .switch input:checked + .slider { background:linear-gradient(135deg,#60a5fa,#a78bfa); }
    .switch input:checked + .slider::before { transform:translateX(22px); }
    .nav { margin:0 0 18px; }
    .nav-menu { display:flex; gap:8px; flex-wrap:wrap; }
    .nav-toggle { display:none; }
    .nav-link { min-height:36px; padding:8px 12px; border-radius:8px; background:var(--panel); border:1px solid var(--border); color:var(--text); text-decoration:none; font-size:13px; font-weight:700; display:inline-flex; align-items:center; justify-content:center; }
    .nav-link.active { color:white; background:var(--button-bg); border:1px solid transparent; }
    .card { background:var(--panel); border:1px solid var(--border); border-radius:8px; box-shadow:var(--shadow); padding:16px; margin-bottom:14px; }
    textarea, input { width:100%; padding:10px 12px; border:1px solid var(--border); border-radius:8px; background:var(--panel-soft); color:var(--text); margin-bottom:10px; }
    textarea { min-height:120px; resize:vertical; }
    button { min-height:40px; padding:8px 14px; border:none; border-radius:8px; color:white; background:var(--button-bg); font-weight:700; cursor:pointer; }
    table { width:100%; border-collapse:collapse; }
    td, th { padding:12px; border-top:1px solid var(--border); text-align:left; overflow-wrap:anywhere; word-break:break-word; }
    th { background:var(--panel-soft); color:var(--muted); }
    .ok { color:#16a34a; font-weight:800; }
    .bad { color:var(--danger); font-weight:800; }
    .step { display:flex; align-items:center; gap:10px; padding:10px 0; border-top:1px solid var(--border); }
    .badge { min-width:56px; padding:5px 8px; border-radius:999px; font-size:12px; font-weight:800; text-align:center; }
    .hit { background:#dcfce7; color:#15803d; }
    .miss { background:#fee2e2; color:#b91c1c; }
    @media (max-width:860px) { body { padding:14px; } .topbar { flex-direction:column; align-items:stretch; } .theme-control { width:100%; justify-content:space-between; } h2 { font-size:24px; } .nav-toggle { display:flex; width:100%; min-height:40px; padding:8px 12px; border-radius:8px; border:1px solid var(--border); background:var(--panel); color:var(--text); font-weight:700; align-items:center; justify-content:space-between; } .nav-menu { display:none; grid-template-columns:1fr; gap:8px; margin-top:8px; } .nav.open .nav-menu { display:grid; } .nav-link { width:100%; } table, tbody, tr, td { display:block; width:100%; } table { background:transparent; } tr { border:1px solid var(--border); border-radius:8px; overflow:hidden; margin-bottom:12px; background:var(--panel); } tr:first-child { display:none; } td { display:grid; grid-template-columns:112px minmax(0, 1fr); gap:10px; } td::before { content:attr(data-label); color:var(--muted); font-weight:700; } }
    """


@app.get("/login", response_class=HTMLResponse)
def login_page(error: str = ""):
    has_users = bool(load_admin_users())
    title = "後台登入" if has_users else "建立第一位管理員"
    button = "登入" if has_users else "建立管理員"
    hint = "請輸入管理員帳號密碼。" if has_users else "目前尚未建立管理員，請先建立第一位管理員。"

    return HTMLResponse(f"""
    <html><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/><style>{admin_css()}</style></head>
    <body><main class="page" style="max-width:460px;">
    <div class="card" style="margin-top:12vh;">
        <h2>{html_escape(title)}</h2>
        <p class="subtitle">{html_escape(hint)}</p>
        {f'<p class="bad">{html_escape(error)}</p>' if error else ''}
        <form method="post" action="/login" style="margin-top:18px;">
            <input name="username" placeholder="帳號" autocomplete="username" required>
            <input name="password" type="password" placeholder="密碼" autocomplete="current-password" required>
            <button style="width:100%;">{html_escape(button)}</button>
        </form>
    </div>
    </main></body></html>
    """)


@app.post("/login")
def login(username: str = Form(...), password: str = Form(...)):
    username = username.strip()
    users = load_admin_users()

    if not users:
        if len(username) < 3 or len(password) < 8:
            return RedirectResponse("/login?error=帳號至少 3 碼，密碼至少 8 碼", status_code=302)

        users.append({
            "username": username,
            "password_hash": hash_password(password),
            "created_at": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
        })
        save_admin_users(users)
    else:
        matched = next((user for user in users if user.get("username") == username), None)

        if not matched or not verify_password(password, matched.get("password_hash", "")):
            return RedirectResponse("/login?error=帳號或密碼錯誤", status_code=302)

    response = RedirectResponse("/", status_code=302)
    response.set_cookie(
        AUTH_COOKIE,
        make_auth_token(username),
        max_age=AUTH_MAX_AGE,
        httponly=True,
        samesite="lax",
    )
    return response


@app.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie(AUTH_COOKIE)
    return response


@app.get("/admin/users", response_class=HTMLResponse)
def admin_users_page(request: Request):
    admin = current_admin(request) or "-"
    users = load_admin_users()
    rows = ""

    for user in users:
        username = user.get("username", "")
        can_delete = len(users) > 1 and username != admin
        delete_html = (
            f'<a class="bad" href="/admin/users/delete/{html_escape(username)}" '
            f'onclick="return confirm(\'確定要刪除這個管理員嗎？\')">刪除</a>'
            if can_delete else "-"
        )
        rows += f"""
        <tr>
            <td data-label="帳號">{html_escape(username)}</td>
            <td data-label="建立時間">{html_escape(user.get('created_at', '-'))}</td>
            <td data-label="操作">
                {delete_html}
            </td>
        </tr>
        """

    return HTMLResponse(f"""
    <html><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/><style>{admin_css()}</style></head>
    <body><main class="page">
    <header class="topbar">
        <div>
            <h2>帳號管理</h2>
            <p class="subtitle">管理後台登入帳號，目前登入：{html_escape(admin)}</p>
        </div>
        <a class="nav-link" href="/logout">登出</a>
    </header>
    <nav class="nav">{admin_nav("帳號管理")}</nav>
    <section class="card">
        <h3>新增管理員</h3>
        <form method="post" action="/admin/users/add">
            <input name="username" placeholder="帳號" required>
            <input name="password" type="password" placeholder="密碼，至少 8 碼" required>
            <button>新增管理員</button>
        </form>
    </section>
    <section class="card">
        <h3>修改我的密碼</h3>
        <form method="post" action="/admin/users/password">
            <input name="old_password" type="password" placeholder="目前密碼" required>
            <input name="new_password" type="password" placeholder="新密碼，至少 8 碼" required>
            <button>更新密碼</button>
        </form>
    </section>
    <section class="card">
        <h3>管理員清單</h3>
        <table><tr><th>帳號</th><th>建立時間</th><th>操作</th></tr>{rows}</table>
    </section>
    </main></body></html>
    """)


@app.post("/admin/users/add")
def add_admin_user(username: str = Form(...), password: str = Form(...)):
    username = username.strip()
    users = load_admin_users()

    if len(username) >= 3 and len(password) >= 8 and not any(user.get("username") == username for user in users):
        users.append({
            "username": username,
            "password_hash": hash_password(password),
            "created_at": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
        })
        save_admin_users(users)

    return RedirectResponse("/admin/users", status_code=302)


@app.post("/admin/users/password")
def change_admin_password(
    request: Request,
    old_password: str = Form(...),
    new_password: str = Form(...)
):
    admin = current_admin(request)
    users = load_admin_users()

    for user in users:
        if user.get("username") == admin and verify_password(old_password, user.get("password_hash", "")) and len(new_password) >= 8:
            user["password_hash"] = hash_password(new_password)
            save_admin_users(users)
            break

    return RedirectResponse("/admin/users", status_code=302)


@app.get("/admin/users/delete/{username}")
def delete_admin_user(request: Request, username: str):
    admin = current_admin(request)
    users = load_admin_users()

    if username != admin and len(users) > 1:
        users = [user for user in users if user.get("username") != username]
        save_admin_users(users)

    return RedirectResponse("/admin/users", status_code=302)


def trace_reply_flow(message):
    steps = []

    faq, _ = search_faq(message)
    steps.append(("FAQ", bool(faq), "命中 FAQ" if faq else "未命中"))

    company, _ = handle_company(message)
    steps.append(("公司資料", bool(company), "命中 company.json" if company else "未命中"))

    kb, kb_source = search_knowledge(message)
    steps.append(("KB", bool(kb), kb_source if kb else "未命中"))

    indexed_answer, indexed_source = search_site_index(message)
    steps.append(("網站索引", bool(indexed_answer), indexed_source if indexed_answer else "未命中或低信心"))

    url_data = search_urls(message)
    steps.append(("即時網站搜尋", bool(url_data), url_data.get("title", "命中") if url_data else "未命中 urls.json keywords"))

    return steps


@app.get("/test-chat", response_class=HTMLResponse)
def test_chat_page(message: str = ""):
    answer = ""
    source = ""
    trace_html = ""

    if message:
        steps = trace_reply_flow(message)
        answer, source = ai_reply(message)
        trace_html = "".join(
            f"""
            <div class="step">
                <span class="badge {'hit' if hit else 'miss'}">{'命中' if hit else '略過'}</span>
                <b>{html_escape(name)}</b>
                <span>{html_escape(detail)}</span>
            </div>
            """
            for name, hit, detail in steps
        )

    result_html = ""
    if answer:
        result_html = f"""
        <div class="card">
            <h3>命中流程</h3>
            {trace_html}
        </div>
        <div class="card">
            <h3>測試結果</h3>
            <p><b>資料來源：</b>{html_escape(source)}</p>
            <div style="white-space:pre-wrap; line-height:1.7;">{html_escape(answer)}</div>
        </div>
        """

    return HTMLResponse(f"""
    <html><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/><style>{admin_css()}</style></head>
    <body><main class="page">
    <header class="topbar">
        <div>
            <h2>LINE 問答測試</h2>
            <p class="subtitle">不用打開 LINE，直接測目前 AI 客服回答流程</p>
        </div>
        <label class="theme-control">
            <span>深夜模式</span>
            <span class="switch">
                <input id="theme-toggle" type="checkbox" onchange="toggleTheme()">
                <span class="slider"></span>
            </span>
        </label>
    </header>
    <nav class="nav">{admin_nav("測試")}</nav>
    <form class="card" method="get" action="/test-chat">
        <textarea name="message" placeholder="輸入測試問題">{html_escape(message)}</textarea>
        <button>送出測試</button>
    </form>
    {result_html}
    <script>
    (function(){{
        const savedTheme = localStorage.getItem("test-theme");
        if(savedTheme === "dark"){{
            document.body.classList.add("dark");
        }}
    }})();

    document.addEventListener("DOMContentLoaded", function(){{
        const toggle = document.getElementById("theme-toggle");
        if(toggle){{
            toggle.checked = document.body.classList.contains("dark");
        }}
    }});

    function toggleTheme(){{
        const toggle = document.getElementById("theme-toggle");
        const isDark = toggle ? toggle.checked : !document.body.classList.contains("dark");
        document.body.classList.toggle("dark", isDark);
        localStorage.setItem("test-theme", isDark ? "dark" : "light");
    }}
    </script>
    </main></body></html>
    """)


def html_escape(value):
    import html
    return html.escape(str(value))


def source_items(source):
    if not source:
        return []

    raw = str(source)

    if raw.startswith("網站索引 - "):
        raw = raw.replace("網站索引 - ", "", 1).strip()

    parts = [part.strip() for part in raw.split(",") if part.strip()]
    items = []

    for part in parts:
        if part not in items:
            items.append(part)

    return items


def source_references(source):
    items = source_items(source)
    source_text = str(source or "")
    refs = []
    title_map = {}

    if os.path.exists(SITE_INDEX_FILE):
        try:
            with open(SITE_INDEX_FILE, "r", encoding="utf-8") as f:
                for item in json.load(f):
                    url = item.get("url")
                    if url and url not in title_map:
                        title_map[url] = item.get("title") or item.get("site") or url
        except:
            title_map = {}

    for item in items:
        if item.startswith("http"):
            refs.append({
                "type": "網站",
                "title": title_map.get(item, item),
                "url": item
            })
        elif item.startswith("KB-"):
            refs.append({"type": "KB", "title": item.replace("KB-", "知識庫：", 1), "url": ""})
        elif "KB" in source_text:
            refs.append({"type": "KB", "title": item, "url": ""})
        elif item in {"FAQ", "COMPANY"}:
            refs.append({"type": item, "title": "FAQ" if item == "FAQ" else "公司資料", "url": ""})

    return refs


def classify_lead(message, reply="", source=""):
    text = f"{message} {reply}".lower()
    rules = [
        ("詢價", 45, ["價格", "費用", "報價", "多少錢", "price", "quote", "quotation", "cost"]),
        ("授權", 40, ["授權", "license", "續約", "renewal", "key"]),
        ("試用", 40, ["試用", "demo", "poc", "評估", "下載試用", "trial"]),
        ("產品比較", 35, ["比較", "差異", "vs", "對比", "哪個好", "替代", "競品"]),
        ("導入建議", 35, ["導入", "建置", "部署", "規劃", "方案", "implementation", "migration"]),
        ("業務聯絡", 50, ["業務", "專人", "聯絡我", "聯繫我", "有人聯絡", "contact", "sales"]),
    ]
    score = 0
    intents = []
    reasons = []

    for intent, weight, keywords in rules:
        hits = [keyword for keyword in keywords if keyword in text]

        if hits:
            intents.append(intent)
            score += weight
            reasons.append(f"{intent}：{', '.join(hits[:3])}")

    no_answer_markers = ["沒有相關資訊", "目前知識庫沒有", "目前網站索引沒有", "無法根據"]

    if str(source) == "AI客服" or any(marker in str(reply) for marker in no_answer_markers):
        score += 20
        reasons.append("回答信心較低")

    score = min(score, 100)
    followup_intents = {"詢價", "授權", "試用", "業務聯絡"}
    need_followup = score >= 70 or any(intent in followup_intents for intent in intents)

    if not intents:
        intents = ["一般詢問"]

    return {
        "intent": "、".join(dict.fromkeys(intents)),
        "lead_score": score,
        "lead_reason": "；".join(reasons),
        "need_followup": need_followup,
        "followup_status": "pending" if need_followup else "none"
    }


def apply_handoff_message(reply, lead):
    if not lead.get("need_followup"):
        return reply

    handoff = "我可以先幫您整理初步資訊，也建議由專人協助確認需求。"

    if handoff in reply:
        return reply

    return f"{reply}\n\n{handoff}"


def contact_payload(payload):
    return {
        "contact_name": str(payload.get("name", "")).strip(),
        "contact_company": str(payload.get("company", "")).strip(),
        "contact_phone": str(payload.get("phone", "")).strip(),
        "contact_email": str(payload.get("email", "")).strip(),
        "contact_need": str(payload.get("need", "")).strip(),
    }


async def web_chat_response(request: Request):
    start = time.time()

    try:
        payload = await request.json()
    except:
        raise HTTPException(status_code=400, detail="JSON 格式錯誤")

    message = str(payload.get("message", "")).strip()
    session_id = str(payload.get("session_id", "web")).strip() or "web"

    if not message:
        raise HTTPException(status_code=400, detail="請輸入問題")

    reply, source = ai_reply(message)
    lead = classify_lead(message, reply, source)
    reply = apply_handoff_message(reply, lead)
    latency = round(time.time() - start, 3)

    save_log(
        session_id,
        message,
        reply,
        request,
        "WEB",
        latency,
        source,
        lead
    )

    return {
        "reply": reply,
        "source": source,
        "used_sources": source_items(source),
        "references": source_references(source),
        "intent": lead["intent"],
        "lead_score": lead["lead_score"],
        "need_followup": lead["need_followup"],
        "latency": latency
    }


@app.post("/chat")
async def web_chat(request: Request):
    return await web_chat_response(request)


@app.post("/web/chat")
async def web_chat_alias(request: Request):
    return await web_chat_response(request)


@app.post("/web/image")
async def web_image(
    request: Request,
    file: UploadFile = File(...),
    session_id: str = Form("web")
):
    start = time.time()
    content = await file.read()

    if not content:
        raise HTTPException(status_code=400, detail="圖片內容是空的")

    analysis = analyze_image(content, file.filename, file.content_type or "image/jpeg")

    if analysis["ok"]:
        reply, source, message = answer_image_question(analysis["text"])
    else:
        reply = analysis["message"]
        source = "IMAGE"
        message = "使用者上傳圖片，但圖片辨識尚未設定。"

    latency = round(time.time() - start, 3)
    lead = classify_lead(message, reply, source)
    reply = apply_handoff_message(reply, lead)

    save_log(
        session_id or "web",
        message,
        reply,
        request,
        "WEB",
        latency,
        source,
        lead,
        {
            "attachment_type": "image",
            "attachment_path": analysis.get("image_path", ""),
            "image_text": analysis.get("text", ""),
        }
    )

    return {
        "reply": reply,
        "source": source,
        "image_text": analysis.get("text", ""),
        "image_ready": analysis["ok"],
        "latency": latency
    }


@app.post("/web/lead")
async def web_lead(request: Request):
    start = time.time()

    try:
        payload = await request.json()
    except:
        raise HTTPException(status_code=400, detail="JSON 格式錯誤")

    session_id = str(payload.get("session_id", "web")).strip() or "web"
    contact = contact_payload(payload)

    if not (contact["contact_phone"] or contact["contact_email"]):
        raise HTTPException(status_code=400, detail="請至少留下電話或 Email")

    need_text = contact["contact_need"] or "使用者留下聯絡資訊，請專人追蹤。"
    message = "WEB 表單：使用者留下聯絡資訊"
    reply = "已收到您的聯絡資訊，我們會請專人協助確認需求。"
    lead = {
        "intent": "業務聯絡",
        "lead_score": 100,
        "lead_reason": "使用者主動留下 WEB 聯絡表單",
        "need_followup": True,
        "followup_status": "pending"
    }

    save_log(
        session_id,
        message,
        reply,
        request,
        "WEB",
        round(time.time() - start, 3),
        "WEB 表單",
        lead,
        {
            **contact,
            "contact_need": need_text,
        }
    )

    return {
        "ok": True,
        "reply": reply
    }


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
        f"<tr><td data-label='項目'>{html_escape(name)}</td><td data-label='狀態' class='{'ok' if ok else 'bad'}'>{'OK' if ok else '缺少'}</td></tr>"
        for name, ok in checks
    )
    return HTMLResponse(f"""
    <html><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/><style>{admin_css()}</style></head>
    <body><main class="page">
    <h2>健康檢查</h2><p class="subtitle">確認服務設定與必要資料檔是否存在</p>
    <nav class="nav">{admin_nav("健康檢查")}</nav>
    <div class="card"><table><tr><th>項目</th><th>狀態</th></tr>{rows}</table></div>
    </main></body></html>
    """)


# =========================
# LOG SAVE
# =========================
def save_log(user, message, reply, request: Request, platform, latency, source, lead=None, extra=None):

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

    lead = lead or classify_lead(message, reply, source)

    row = {
        "id": len(logs) + 1,
        "time": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
        "user": user,
        "message": message,
        "reply": reply,
        "platform": platform,
        "latency": latency,
        "ip": ip,
        "source": source,
        "intent": lead.get("intent", "一般詢問"),
        "lead_score": lead.get("lead_score", 0),
        "lead_reason": lead.get("lead_reason", ""),
        "need_followup": lead.get("need_followup", False),
        "followup_status": lead.get("followup_status", "none")
    }

    if extra:
        row.update(extra)

    logs.append(row)

    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)


def get_line_profile(user_id):
    if not user_id:
        return {}

    profile = {"line_user_id": user_id}

    try:
        line_profile = line_bot_api.get_profile(user_id)
        profile.update({
            "line_display_name": getattr(line_profile, "display_name", ""),
            "line_picture_url": getattr(line_profile, "picture_url", ""),
            "line_status_message": getattr(line_profile, "status_message", ""),
            "line_language": getattr(line_profile, "language", "")
        })
    except Exception as exc:
        profile["line_profile_error"] = str(exc)

    return profile


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

        message_type = event["message"].get("type")
        user_id = event["source"].get("userId")
        line_profile = get_line_profile(user_id)

        platform = detect_platform(request)

        if message_type == "text":
            user_msg = event["message"]["text"]
            reply, source = ai_reply(user_msg)
            image_extra = {}
        elif message_type == "image":
            message_id = event["message"].get("id")
            image_content = line_bot_api.get_message_content(message_id)
            chunks = []

            for chunk in image_content.iter_content():
                chunks.append(chunk)

            content = b"".join(chunks)
            analysis = analyze_image(content, f"line_{message_id}.jpg", "image/jpeg")

            if analysis["ok"]:
                reply, source, user_msg = answer_image_question(analysis["text"])
            else:
                reply = analysis["message"]
                source = "IMAGE"
                user_msg = "使用者傳送圖片，但圖片辨識尚未設定。"

            image_extra = {
                "attachment_type": "image",
                "attachment_path": analysis.get("image_path", ""),
                "image_text": analysis.get("text", ""),
            }
        else:
            continue

        lead = classify_lead(user_msg, reply, source)
        reply = apply_handoff_message(reply, lead)

        latency = round(time.time() - start, 3)

        final_reply = f"{reply}\n\n資料來源：{source}"

        line_bot_api.reply_message(
            event["replyToken"],
            TextSendMessage(text=final_reply[:1000])
        )

        extra = {}
        extra.update(line_profile)
        extra.update(image_extra)

        save_log(
            user_id,
            user_msg,
            reply,
            request,
            platform,
            latency,
            source,
            lead,
            extra
        )

    return {"status": "ok"}
