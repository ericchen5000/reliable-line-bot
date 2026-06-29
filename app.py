from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
import sqlite3
import json
import os
from datetime import datetime

app = FastAPI()

DB_PATH = "data.db"
LOG_PATH = "logs/chat_logs.json"


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
# INIT LOG FILE
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
        <h1>FAQ</h1>

        <form method="post" action="/faq/add">
            問題:<br>
            <input name="question"><br><br>

            答案:<br>
            <textarea name="answer"></textarea><br><br>

            <button type="submit">新增</button>
        </form>

        <hr>
        <a href="/faq/list">查看 FAQ</a>
    </body>
    </html>
    """


@app.post("/faq/add")
async def add_faq(question: str = Form(...), answer: str = Form(...)):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("INSERT INTO faq (question, answer) VALUES (?, ?)", (question, answer))

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
            <b>ID:</b> {r[0]}<br>
            <b>Q:</b> {r[1]}<br>
            <b>A:</b> {r[2]}<br>
        </div>
        <hr>
        """

    return HTMLResponse(html)


@app.get("/faq/delete/{faq_id}")
def delete_faq(faq_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("DELETE FROM faq WHERE id = ?", (faq_id,))

    conn.commit()
    conn.close()

    return {"deleted": faq_id}


# =========================
# FAQ API (給 LINE / AI 用)
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
# LOG SAVE (SAFE)
# =========================
def save_log(user="", message="", reply=""):
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
# LOG VIEW (FIXED - NO CRASH)
# =========================
@app.get("/logs", response_class=HTMLResponse)
def view_logs():
    init_log()

    with open(LOG_PATH, "r", encoding="utf-8") as f:
        logs = json.load(f)

    html = "<h1>LOGS</h1><hr>"

    for l in reversed(logs):
        html += f"""
        <div>
            <b>Time:</b> {l.get('time','')}<br>
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


# =========================
# LINE WEBHOOK (FIXED - NO 404)
# =========================
@app.post("/line/webhook")
async def line_webhook(request: Request):
    data = await request.json()

    print("LINE WEBHOOK:", data)

    # LINE 先回 200（避免 404）
    return {"status": "ok"}