from fastapi import FastAPI, Request, HTTPException
from linebot import LineBotApi, WebhookHandler
from linebot.models import TextSendMessage
import json
import os
import time
from datetime import datetime
from urllib.parse import urlparse

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

app.include_router(logs_router)
app.include_router(faq_router)

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

LOG_PATH = "logs/chat_logs.json"


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
# URL SEARCH (NEW)
# =========================
def search_urls(user_message):
    path = "data/urls.json"

    if not os.path.exists(path):
        return None, None

    try:
        with open(path, "r", encoding="utf-8") as f:
            urls = json.load(f)
    except:
        return None, None

    msg = user_message.lower()

    for item in urls:
        keywords = item.get("keywords", [])
        url = item.get("url", "")
        title = item.get("title", "")

        if any(k in msg for k in keywords):
            domain = urlparse(url).netloc.replace("www.", "")
            source = "URL-" + domain.split(".")[0]
            return f"{title}: {url}", source

    return None, None


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
# PRODUCTS (已停止搶 KB)
# =========================
def handle_products(user_message):
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
            if not file.endswith(".txt"):
                continue

            path = os.path.join(root, file)

            with open(path, "r", encoding="utf-8") as f:
                content = f.read().lower()

                if msg in content:
                    results.append((content[:1000], file))

    if results:
        text = "\n\n---\n\n".join([r[0] for r in results[:2]])

        names = [os.path.splitext(r[1])[0] for r in results[:2]]
        source = "KB-" + ",".join(names)

        return text, source

    return None, None


# =========================
# AI FALLBACK
# =========================
def ai_fallback(user_message):
    prompt = SYSTEM_PROMPT + """

規則：
1. 不可亂編
2. 沒資料就回答：目前資料庫中沒有相關資訊
3. 使用繁體中文
4. 簡短回答
"""

    return ask_deepseek(prompt, user_message), "AI"


# =========================
# ROUTER (FAQ → URL → KB → COMPANY → AI)
# =========================
def ai_reply(user_message):

    faq, _ = search_faq(user_message)
    if faq:
        return faq, "FAQ"

    url, src = search_urls(user_message)
    if url:
        return url, src

    kb, src = search_knowledge(user_message)
    if kb:
        return kb, src

    company, _ = handle_company(user_message)
    if company:
        return company, "COMPANY"

    reply, _ = ai_fallback(user_message)
    return reply, "AI"


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

    ua = request.headers.get("user-agent", "")

    ip = request.headers.get("x-forwarded-for")
    if not ip:
        ip = request.client.host if request.client else "-"

    logs.append({
        "id": len(logs) + 1,
        "time": datetime.now().isoformat(),

        "user": user,
        "message": message,
        "reply": reply,

        "platform": platform,
        "latency": latency,

        "ip": ip,
        "source": source,

        "meta": {
            "user_agent": ua,
            "device": detect_device(request),
            "browser": detect_browser(request)
        }
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