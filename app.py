from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
import sqlite3
import json
import os
from datetime import datetime
import requests
from dotenv import load_dotenv

# =========================
# ENV
# =========================
load_dotenv()

app = FastAPI()

DB_PATH = "data.db"
LOG_PATH = "logs/chat_logs.json"
KB_PATH = "knowledge"

LINE_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")


# =========================
# INIT DB
# =========================
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS faq (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        question TEXT,
        answer TEXT
    )
    """)

    conn.commit()
    conn.close()


# =========================
# INIT LOG
# =========================
def init_log():
    os.makedirs("logs", exist_ok=True)
    if not os.path.exists(LOG_PATH):
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            json.dump([], f)


init_db()
init_log()


# =========================
# LOG SAVE
# =========================
def save_log(user, msg, reply):
    init_log()

    with open(LOG_PATH, "r", encoding="utf-8") as f:
        logs = json.load(f)

    logs.append({
        "time": datetime.now().isoformat(),
        "user": user,
        "message": msg,
        "reply": reply
    })

    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)


# =========================
# FAQ
# =========================
def faq_search(text):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT answer FROM faq WHERE question LIKE ?", (f"%{text}%",))
    row = c.fetchone()

    conn.close()

    return row[0] if row else None


# =========================
# 🔥 KB（已接上）
# =========================
def kb_search(text):
    if not os.path.exists(KB_PATH):
        return None

    for file in os.listdir(KB_PATH):
        path = os.path.join(KB_PATH, file)

        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()

                if text.lower() in content.lower():
                    return content[:800]

        except:
            continue

    return None


# =========================
# AI（DeepSeek）
# =========================
def ai_answer(text):
    try:
        url = "https://api.deepseek.com/chat/completions"

        headers = {
            "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
            "Content-Type": "application/json"
        }

        data = {
            "model": "deepseek-chat",
            "messages": [
                {"role": "system", "content": "你是企業AI客服，用繁體中文回答"},
                {"role": "user", "content": text}
            ]
        }

        r = requests.post(url, headers=headers, json=data)
        return r.json()["choices"][0]["message"]["content"]

    except Exception as e:
        return f"AI error: {str(e)}"


# =========================
# 🚀 三層 Fallback（FAQ → KB → AI）
# =========================
def answer_engine(text):

    # 1️⃣ FAQ
    faq = faq_search(text)
    if faq:
        return faq

    # 2️⃣ KB
    kb = kb_search(text)
    if kb:
        return kb

    # 3️⃣ AI
    return ai_answer(text)


# =========================
# LINE REPLY
# =========================
def reply_line(token, text):

    if not LINE_TOKEN:
        print("❌ LINE TOKEN missing")
        return

    url = "https://api.line.me/v2/bot/message/reply"

    headers = {
        "Authorization": f"Bearer {LINE_TOKEN}",
        "Content-Type": "application/json"
    }

    data = {
        "replyToken": token,
        "messages": [{"type": "text", "text": text[:1000]}]
    }

    requests.post(url, headers=headers, json=data)


# =========================
# WEBHOOK
# =========================
@app.post("/line/webhook")
async def webhook(request: Request):

    body = await request.json()
    event = body["events"][0]

    text = event["message"]["text"]
    token = event["replyToken"]
    user = event["source"]["userId"]

    # 🔥 核心：三層 AI
    reply = answer_engine(text)

    reply_line(token, reply)
    save_log(user, text, reply)

    return {"status": "ok"}


# =========================
# LOG UI
# =========================
@app.get("/logs", response_class=HTMLResponse)
def logs():

    with open(LOG_PATH, "r", encoding="utf-8") as f:
        logs = json.load(f)

    html = "<h1>LOGS</h1><hr>"

    for l in reversed(logs):
        html += f"""
        <div>
            <b>User:</b> {l["user"]}<br>
            <b>Msg:</b> {l["message"]}<br>
            <b>Reply:</b> {l["reply"]}<br>
        </div>
        <hr>
        """

    return HTMLResponse(html)