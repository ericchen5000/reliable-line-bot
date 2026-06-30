from fastapi import APIRouter, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
import json
import os

router = APIRouter()

FAQ_PATH = "data/faq.json"


# =========================
# LOAD
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
# SAVE
# =========================
def save_faq(data):
    os.makedirs(os.path.dirname(FAQ_PATH), exist_ok=True)
    with open(FAQ_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# =========================
# MAIN PAGE (ALL IN ONE)
# =========================
@router.get("/faq", response_class=HTMLResponse)
def faq_page(edit_id: int = None):

    faq = load_faq()

    edit_item = None
    if edit_id is not None and 0 <= edit_id < len(faq):
        edit_item = faq[edit_id]

    rows = ""

    for i, item in enumerate(faq):
        rows += f"""
        <tr>
            <td>{i+1}</td>
            <td>{item.get('question','')}</td>
            <td>{item.get('answer','')}</td>

            <td>
                <a href="/faq?edit_id={i}" class="btn-edit">編輯</a>
                <a href="/faq/delete/{i}" class="btn-del">刪除</a>
            </td>
        </tr>
        """

    # =========================
    # FORM MODE
    # =========================
    is_edit = edit_item is not None

    form_action = "/faq/add"
    form_title = "新增 FAQ"
    btn_text = "新增"

    q_val = ""
    a_val = ""

    if is_edit:
        form_action = f"/faq/edit/{edit_id}"
        form_title = "編輯 FAQ"
        btn_text = "更新"
        q_val = edit_item.get("question", "")
        a_val = edit_item.get("answer", "")

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

        .layout {{
            display:grid;
            grid-template-columns: 1fr 2fr;
            gap:20px;
        }}

        .card {{
            background:white;
            padding:16px;
            border-radius:16px;
            box-shadow:0 6px 18px rgba(0,0,0,0.05);
        }}

        input, textarea {{
            width:100%;
            padding:10px;
            margin-bottom:10px;
            border-radius:12px;
            border:1px solid #e5e7eb;
        }}

        button {{
            padding:10px 14px;
            border:none;
            border-radius:999px;
            background:linear-gradient(135deg,#60a5fa,#a78bfa);
            color:white;
            cursor:pointer;
        }}

        table {{
            width:100%;
            border-collapse:collapse;
        }}

        th {{
            text-align:left;
            background:#eef2ff;
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

        .top-title {{
            font-weight:700;
            margin-bottom:10px;
        }}
    </style>
    </head>

    <body>

    <h2>FAQ 管理中心</h2>

    <div class="layout">

        <!-- LEFT: FORM -->
        <div class="card">
            <div class="top-title">{form_title}</div>

            <form method="post" action="{form_action}">
                <input name="question" placeholder="問題" value="{q_val}" required>
                <textarea name="answer" placeholder="答案" required>{a_val}</textarea>

                <button>{btn_text}</button>
            </form>
        </div>

        <!-- RIGHT: TABLE -->
        <div class="card">
            <table>
                <tr>
                    <th>ID</th>
                    <th>問題</th>
                    <th>答案</th>
                    <th>操作</th>
                </tr>
                {rows}
            </table>
        </div>

    </div>

    </body>
    </html>
    """)


# =========================
# ADD
# =========================
@router.post("/faq/add")
def add(question: str = Form(...), answer: str = Form(...)):

    faq = load_faq()

    faq.append({
        "question": question,
        "answer": answer
    })

    save_faq(faq)

    return RedirectResponse("/faq", status_code=302)


# =========================
# EDIT
# =========================
@router.post("/faq/edit/{idx}")
def edit(idx: int, question: str = Form(...), answer: str = Form(...)):

    faq = load_faq()

    if 0 <= idx < len(faq):
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
def delete(idx: int):

    faq = load_faq()

    if 0 <= idx < len(faq):
        faq.pop(idx)

    save_faq(faq)

    return RedirectResponse("/faq", status_code=302)