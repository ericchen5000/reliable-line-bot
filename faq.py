from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
import json
import os

router = APIRouter()

FAQ_PATH = "data/faq.json"


# =========================
# LOAD FAQ
# =========================
def load_faq():
    if not os.path.exists(FAQ_PATH):
        return []
    try:
        with open(FAQ_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


# =========================
# SAVE FAQ
# =========================
def save_faq(data):
    os.makedirs(os.path.dirname(FAQ_PATH), exist_ok=True)
    with open(FAQ_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# =========================
# LIST UI
# =========================
@router.get("/faq", response_class=HTMLResponse)
def faq_ui():

    faq = load_faq()

    rows = ""

    for i, item in enumerate(faq):
        rows += f"""
        <tr>
            <td>{i+1}</td>
            <td>{item.get('question','')}</td>
            <td>{item.get('answer','')}</td>

            <td>
                <a href="/faq/edit/{i}" class="btn-edit">編輯</a>
                <a href="/faq/delete/{i}" class="btn-del">刪除</a>
            </td>
        </tr>
        """

    return HTMLResponse(f"""
    <html>
    <head>
    <meta charset="utf-8"/>

    <style>
        body {{
            margin:0;
            font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC";
            background:#f5f7fb;
            padding:20px;
        }}

        h2 {{
            margin-bottom:10px;
        }}

        .top {{
            margin-bottom:10px;
        }}

        .btn-add {{
            padding:10px 14px;
            background:linear-gradient(135deg,#60a5fa,#a78bfa);
            color:white;
            border-radius:999px;
            text-decoration:none;
        }}

        table {{
            width:100%;
            border-collapse:collapse;
            background:white;
            border-radius:12px;
            overflow:hidden;
        }}

        th {{
            background:#eef2ff;
            text-align:left;
            padding:10px;
        }}

        td {{
            padding:10px;
            border-top:1px solid #eee;
        }}

        .btn-edit {{
            padding:6px 10px;
            background:#3b82f6;
            color:white;
            border-radius:999px;
            text-decoration:none;
            font-size:12px;
        }}

        .btn-del {{
            padding:6px 10px;
            background:#ef4444;
            color:white;
            border-radius:999px;
            text-decoration:none;
            font-size:12px;
        }}
    </style>
    </head>

    <body>

    <h2>FAQ 管理</h2>

    <div class="top">
        <a class="btn-add" href="/faq/add">+ 新增 FAQ</a>
    </div>

    <table>
        <tr>
            <th>ID</th>
            <th>問題</th>
            <th>答案</th>
            <th>操作</th>
        </tr>

        {rows}
    </table>

    </body>
    </html>
    """)


# =========================
# ADD PAGE
# =========================
@router.get("/faq/add", response_class=HTMLResponse)
def add_page():

    return HTMLResponse("""
    <html>
    <body style="font-family:Arial;padding:20px;background:#f5f7fb">

    <h2>新增 FAQ</h2>

    <form method="post" action="/faq/add">
        <input name="question" placeholder="問題" style="width:400px;padding:10px"><br><br>
        <textarea name="answer" placeholder="答案" style="width:400px;height:120px;padding:10px"></textarea><br><br>

        <button style="padding:10px 14px;background:#3b82f6;color:white;border:none;border-radius:999px">
            儲存
        </button>
    </form>

    </body>
    </html>
    """)


# =========================
# ADD POST
# =========================
@router.post("/faq/add")
def add_faq(question: str = Form(...), answer: str = Form(...)):

    faq = load_faq()

    faq.append({
        "question": question,
        "answer": answer
    })

    save_faq(faq)

    return RedirectResponse("/faq", status_code=302)


# =========================
# EDIT PAGE
# =========================
@router.get("/faq/edit/{idx}", response_class=HTMLResponse)
def edit_page(idx: int):

    faq = load_faq()

    item = faq[idx]

    return HTMLResponse(f"""
    <html>
    <body style="font-family:Arial;padding:20px;background:#f5f7fb">

    <h2>編輯 FAQ</h2>

    <form method="post" action="/faq/edit/{idx}">
        <input name="question" value="{item.get('question','')}" style="width:400px;padding:10px"><br><br>
        <textarea name="answer" style="width:400px;height:120px;padding:10px">{item.get('answer','')}</textarea><br><br>

        <button style="padding:10px 14px;background:#f59e0b;color:white;border:none;border-radius:999px">
            更新
        </button>
    </form>

    </body>
    </html>
    """)


# =========================
# EDIT POST
# =========================
@router.post("/faq/edit/{idx}")
def edit_faq(idx: int, question: str = Form(...), answer: str = Form(...)):

    faq = load_faq()

    faq[idx] = {
        "question": question,
        "answer": answer
    }

    save_faq(faq)

    return RedirectResponse("/faq", status_code=302)


# =========================
# DELETE
# =========================
@router.get("/faq/delete/{idx}")
def delete_faq(idx: int):

    faq = load_faq()

    if 0 <= idx < len(faq):
        faq.pop(idx)

    save_faq(faq)

    return RedirectResponse("/faq", status_code=302)