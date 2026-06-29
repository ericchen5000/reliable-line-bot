from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
import sqlite3

app = FastAPI()

DB_PATH = "data.db"


# =========================
# DB INIT
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


init_db()


# =========================
# FAQ UI
# =========================
@app.get("/faq", response_class=HTMLResponse)
def faq_page():
    return """
    <html>
    <head>
        <title>FAQ 管理系統</title>
    </head>
    <body>
        <h1>FAQ 管理</h1>

        <h2>新增 FAQ</h2>

        <form method="post" action="/faq/add">
            問題：<br>
            <input name="question" style="width:400px"><br><br>

            答案：<br>
            <textarea name="answer" style="width:400px;height:120px"></textarea><br><br>

            <button type="submit">新增</button>
        </form>

        <hr>

        <h2>FAQ 列表</h2>
        <a href="/faq/list">查看所有 FAQ</a>

    </body>
    </html>
    """


# =========================
# ADD FAQ
# =========================
@app.post("/faq/add")
async def add_faq(
    question: str = Form(...),
    answer: str = Form(...)
):
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

    html = """
    <html>
    <head><title>FAQ List</title></head>
    <body>
    <h1>FAQ 列表</h1>
    <a href="/faq">回新增頁</a>
    <hr>
    """

    for r in rows:
        html += f"""
        <div style="margin-bottom:20px;">
            <b>ID:</b> {r[0]}<br>
            <b>Q:</b> {r[1]}<br>
            <b>A:</b> {r[2]}<br>
        </div>
        <hr>
        """

    html += "</body></html>"
    return HTMLResponse(content=html)


# =========================
# DELETE FAQ
# =========================
@app.get("/faq/delete/{faq_id}")
def delete_faq(faq_id: int):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("DELETE FROM faq WHERE id = ?", (faq_id,))

    conn.commit()
    conn.close()

    return {"status": "deleted", "id": faq_id}


# =========================
# API (給 AI 用)
# =========================
@app.get("/api/faq")
def api_faq():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    c.execute("SELECT question, answer FROM faq")
    rows = c.fetchall()

    conn.close()

    return JSONResponse([
        {"question": r[0], "answer": r[1]} for r in rows
    ])