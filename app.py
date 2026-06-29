from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from linebot import LineBotApi, WebhookHandler
from linebot.models import TextSendMessage
import json
import os

from config import (
    LINE_CHANNEL_ACCESS_TOKEN,
    LINE_CHANNEL_SECRET,
    FAQ_FILE,
    SYSTEM_PROMPT_FILE,
)

from deepseek import ask_deepseek

app = FastAPI(title="AI Assistant")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)


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
# FAQ
# =========================
def search_faq(question):
    if not FAQ_FILE or not os.path.exists(FAQ_FILE):
        return None

    try:
        with open(FAQ_FILE, "r", encoding="utf-8") as f:
            faq = json.load(f)
    except:
        return None

    q = question.strip().lower()

    for item in faq:
        faq_q = item.get("question", "").strip().lower()
        faq_a = item.get("answer", "")

        if faq_q == q:
            return faq_a

        if faq_q in q or q in faq_q:
            return faq_a

    return None


# =========================
# COMPANY
# =========================
def handle_company(user_message):
    keywords = ["公司", "電話", "地址", "email", "聯絡", "聯絡方式"]

    msg = user_message.lower()

    if any(k in msg for k in keywords):
        path = "data/company.json"
        if not os.path.exists(path):
            return None

        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            return None

        return (
            "公司名稱：" + data.get("company_name", "") + "\n" +
            "電話：" + data.get("phone", "") + "\n" +
            "Email：" + data.get("email", "") + "\n" +
            "地址：" + data.get("address", "") + "\n" +
            "網站：" + data.get("website", "")
        )

    return None


# =========================
# PRODUCTS
# =========================
def handle_products(user_message):
    msg = user_message.lower()

    if "vates" in msg:
        return "VATES = 虛擬化管理平台（XCP-ng / Xen Orchestra）"

    if "array" in msg:
        return "Array Networks = APV / SSL VPN / ZTNA"

    if "penguin" in msg:
        return "Penguin Solutions = 高可用與邊緣運算平台"

    if "neverfail" in msg:
        return "Neverfail = 系統不中斷與災難備援"

    return None


# =========================
# KB
# =========================
def search_knowledge(user_message):
    kb_path = "knowledge"

    if not os.path.exists(kb_path):
        return None

    msg = user_message.lower()
    tokens = [w for w in msg.split() if len(w) > 1]

    results = []

    for root, dirs, files in os.walk(kb_path):
        for file in files:
            if not file.endswith(".txt"):
                continue

            path = os.path.join(root, file)

            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read().lower()

                    if (
                        msg in content
                        or any(t in content for t in tokens)
                        or any(k in content for k in ["vates", "array", "penguin", "neverfail"])
                    ):
                        results.append(content[:1000])

            except:
                continue

    if results:
        return "\n\n---\n\n".join(results[:2])

    return None


# =========================
# AI FALLBACK
# =========================
def ai_fallback(user_message):
    prompt = SYSTEM_PROMPT + """

規則：
1. 不可編造不存在的產品或技術
2. 沒有資料就回答：目前資料庫中沒有相關資訊
3. 不可延伸或解釋未提供內容
4. 使用繁體中文
5. 回答簡短
"""

    return ask_deepseek(prompt, user_message)


# =========================
# ROUTER
# =========================
def ai_reply(user_message):

    faq = search_faq(user_message)
    if faq:
        return faq

    company = handle_company(user_message)
    if company:
        return company

    product = handle_products(user_message)
    if product:
        return product

    kb = search_knowledge(user_message)
    if kb:
        return kb

    return ai_fallback(user_message)


# =========================
# LINE WEBHOOK
# =========================
@app.post("/line/webhook")
async def line_webhook(request: Request):

    body = await request.json()

    if "events" not in body:
        raise HTTPException(status_code=400)

    for event in body["events"]:

        if event.get("type") != "message":
            continue

        if event["message"]["type"] != "text":
            continue

        user_msg = event["message"]["text"]

        reply = ai_reply(user_msg)

        line_bot_api.reply_message(
            event["replyToken"],
            TextSendMessage(text=reply[:1000])
        )

    return {"status": "ok"}


# =========================
# ADMIN (FAQ + LOGS)
# =========================

LOG_PATH = "logs/chat_logs.json"


@app.get("/faq", response_class=HTMLResponse)
def faq_page():

    if not FAQ_FILE or not os.path.exists(FAQ_FILE):
        return HTMLResponse("<h1>No FAQ</h1>")

    with open(FAQ_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    html = "<h1>FAQ</h1><hr>"

    for item in data:
        html += f"""
        <div>
            Q: {item.get('question','')}<br>
            A: {item.get('answer','')}<br>
        </div>
        <hr>
        """

    return HTMLResponse(html)


@app.get("/logs", response_class=HTMLResponse)
def logs_page():

    if not os.path.exists(LOG_PATH):
        return HTMLResponse("<h1>No Logs</h1>")

    with open(LOG_PATH, "r", encoding="utf-8") as f:
        logs = json.load(f)

    html = "<h1>LOGS</h1><hr>"

    for l in reversed(logs):
        html += f"""
        <div>
            <b>User:</b> {l.get('user','')}<br>
            <b>Msg:</b> {l.get('message','')}<br>
            <b>Reply:</b> {l.get('reply','')}<br>
        </div>
        <hr>
        """

    return HTMLResponse(html)