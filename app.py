from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
import sqlite3
import json
import os
from datetime import datetime
import requests

app = FastAPI()

DB_PATH = "data.db"
LOG_PATH = "logs/chat_logs.json"

# ⚠️ LINE TOKEN（請確保這裡是「真的 token」，不是字串）
LINE_TOKEN = "YOUR_LINE_CHANNEL_ACCESS_TOKEN"


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
# ROOT
# =========================
@app.get("/")
def root():
    return {"status": "running"}


# =========================
# FAQ UI
# =========================
@app.get("/faq", response_class=HTMLResponse)
def faq_page():
    return """
    <html>
    <body>
        <h1>FAQ 管理</h1>

        <form method="post" action="/faq/add">
            問題:<br>
            <input name="question"><br><br>

            答案:<br>
            <textarea name="answer"></textarea><br><br>

            <button type="submit">新增</button>
        </form>

        <hr>
        <a href="/faq/list">FAQ LIST</a>
    </body>
    </html>
    """


# =========================
# ADD FAQ
# =========================
@app.post("/faq/add")
async def add_faq(question: str = Form(...), answer: str = Form(...)):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute(
        "INSERT INTO faq (question, answer) VALUES (?, ?)",
        (question, answer)
    )

    conn.commit()
    conn.close()

    return {"status": "ok"}


# =========================
# LIST FAQ
# =========================
@app.get("/faq/list", response_class=HTMLResponse)
def list_faq():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT id, question, answer FROM faq ORDER BY id DESC")
    rows = c.fetchall()

    conn.close()

    html = "<h1>FAQ LIST</h1><hr>"

    for r in rows:
        html += f"""
        <div>
            <b>Q:</b> {r[1]}<br>
            <b>A:</b> {r[2]}<br>
        </div>
        <hr>
        """

    return HTMLResponse(html)


# =========================
# FAQ API
# =========================
@app.get("/api/faq")
def api_faq():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT question, answer FROM faq")
    rows = c.fetchall()

    conn.close()

    return [{"question": r[0], "answer": r[1]} for r in rows]


# =========================
# LOG SAVE
# =========================
def save_log(user, message, reply):
    init_log()

    with open(LOG_PATH, "r", encoding="utf-8") as f:
        logs = json.load(f)

    logs.append({
        "time": datetime.now().isoformat(),
        "user": user or "",
        "message": message or "",
        "reply": reply or ""
    })

    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)


# =========================
# LINE REPLY (DEBUG VERSION - VERY IMPORTANT)
# =========================
def reply_line(reply_token, text):
    url = "https://api.line.me/v2/bot/message/reply"

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_TOKEN}"
    }

    data = {
        "replyToken": reply_token,
        "messages": [
            {"type": "text", "text": text[:1000]}
        ]
    }

    try:
        resp = requests.post(url, headers=headers, json=data)

        # 🔥 這是你現在最關鍵的 debug
        print("===== LINE REPLY DEBUG =====")
        print("STATUS:", resp.status_code)
        print("RESPONSE:", resp.text)
        print("============================")

    except Exception as e:
        print("LINE REQUEST ERROR:", e)


# =========================
# LINE WEBHOOK (SAFE)
# =========================
@app.post("/line/webhook")
async def line_webhook(request: Request):
    try:
        body = await request.json()

        event = body.get("events", [])[0]

        message = event.get("message", {})
        user_text = message.get("text")

        reply_token = event.get("replyToken")
        user_id = event.get("source", {}).get("userId")

        if not user_text:
            return {"status": "ignored"}

        print("USER:", user_text)

        # 👉 暫時 echo（確保流程通）
        reply = f"收到：{user_text}"

        # 回 LINE
        reply_line(reply_token, reply)

        # 存 LOG
        save_log(user_id, user_text, reply)

        return {"status": "ok"}

    except Exception as e:
        print("WEBHOOK ERROR:", e)
        return {"status": "error"}


# =========================
# LOG VIEW
# =========================
@app.get("/logs", response_class=HTMLResponse)
def logs():
    init_log()

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


# =========================
# LOG API
# =========================
@app.get("/api/logs")
def api_logs():
    init_log()

    with open(LOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)