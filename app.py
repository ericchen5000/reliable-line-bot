from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
import sqlite3
import json
import os
from datetime import datetime
import requests
from dotenv import load_dotenv

# =========================
# ENV LOAD（LINE 關鍵）
# =========================
load_dotenv()

app = FastAPI()

DB_PATH = "data.db"
LOG_PATH = "logs/chat_logs.json"

LINE_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_SECRET = os.getenv("LINE_CHANNEL_SECRET")


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
            <input name="question" style="width:400px"><br><br>

            答案:<br>
            <textarea name="answer" style="width:400px;height:120px"></textarea><br><br>

            <button>新增</button>
        </form>

        <hr>
        <a href="/faq/list">FAQ LIST</a>
    </body>
    </html>
    """


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
# LOG SAVE
# =========================
def save_log(user, message, reply):
    init_log()

    with open(LOG_PATH, "r", encoding="utf-8") as f:
        logs = json.load(f)

    logs.append({
        "time": datetime.now().isoformat(),
        "user": user,
        "message": message,
        "reply": reply
    })

    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)


# =========================
# LINE REPLY (已修正 + debug)
# =========================
def reply_line(reply_token, text):

    if not LINE_TOKEN:
        print("❌ LINE TOKEN not loaded")
        return

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

        print("===== LINE DEBUG =====")
        print("STATUS:", resp.status_code)
        print("BODY:", resp.text)
        print("======================")

    except Exception as e:
        print("LINE ERROR:", e)


# =========================
# LINE WEBHOOK（完整保留 + FAQ/KB位置）
# =========================
@app.post("/line/webhook")
async def line_webhook(request: Request):

    try:
        body = await request.json()
        event = body["events"][0]

        msg = event.get("message", {})
        text = msg.get("text")

        reply_token = event.get("replyToken")
        user_id = event.get("source", {}).get("userId")

        if not text:
            return {"status": "ignored"}

        print("USER:", text)

        # =========================
        # 🔥 FAQ 查詢（已恢復）
        # =========================
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        c.execute(
            "SELECT answer FROM faq WHERE question LIKE ?",
            (f"%{text}%",)
        )

        row = c.fetchone()
        conn.close()

        # =========================
        # 🔥 回覆邏輯
        # =========================
        if row:
            reply_text = row[0]
        else:
            reply_text = f"收到：{text}"

        # 回 LINE
        reply_line(reply_token, reply_text)

        # LOG
        save_log(user_id, text, reply_text)

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
# API LOGS
# =========================
@app.get("/api/logs")
def api_logs():
    init_log()

    with open(LOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)