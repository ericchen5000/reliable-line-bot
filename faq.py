from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
import csv
import html
import io
import json
import os
from datetime import datetime
from urllib.parse import urlencode

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
            data = json.load(f)
            return data if isinstance(data, list) else []
    except:
        return []


# =========================
# SAVE
# =========================
def save_faq(data):
    os.makedirs(os.path.dirname(FAQ_PATH), exist_ok=True)
    with open(FAQ_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def e(value):
    return html.escape(str(value))


def nav_html(active=""):
    items = [
        ("/", "Dashboard"),
        ("/logs", "LOGS"),
        ("/faq", "FAQ"),
        ("/weekly-report", "週報"),
        ("/knowledge-gaps", "知識缺口"),
        ("/test-chat", "測試"),
        ("/health", "健康檢查"),
    ]
    return "".join(
        f'<a class="nav-link {"active" if active == label else ""}" href="{href}">{label}</a>'
        for href, label in items
    )


def normalize_question(value):
    return str(value).strip().lower()


# =========================
# MAIN PAGE (ALL IN ONE)
# =========================
@router.get("/faq", response_class=HTMLResponse)
def faq_page(edit_id: int = None, q: str = ""):

    faq = load_faq()
    search_text = q.strip().lower()

    edit_item = None
    if edit_id is not None and 0 <= edit_id < len(faq):
        edit_item = faq[edit_id]

    rows = ""

    for i, item in enumerate(faq):
        if search_text:
            haystack = f"{item.get('question','')} {item.get('answer','')}".lower()
            if search_text not in haystack:
                continue

        edit_query = urlencode({"edit_id": i, "q": q}) if q else urlencode({"edit_id": i})

        rows += f"""
        <tr>
            <td data-label="ID">{i+1}</td>
            <td data-label="問題" class="question-cell">{e(item.get('question',''))}</td>
            <td data-label="答案" class="answer-cell">{e(item.get('answer',''))}</td>

            <td data-label="操作" class="actions">
                <a href="/faq?{e(edit_query)}" class="btn-edit">編輯</a>
                <a href="/faq/delete/{i}" class="btn-del" onclick="return confirm('確定要刪除這筆 FAQ 嗎？')">刪除</a>
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
        :root {{
            --bg: #f6f7fb;
            --panel: #ffffff;
            --panel-soft: #f1f5f9;
            --text: #172033;
            --muted: #64748b;
            --border: #e2e8f0;
            --accent: #4f46e5;
            --accent-strong: #3730a3;
            --accent-soft: #e0e7ff;
            --button-bg: linear-gradient(135deg,#60a5fa,#a78bfa);
            --button-bg-hover: linear-gradient(135deg,#3b82f6,#8b5cf6);
            --danger: #dc2626;
            --shadow: 0 16px 40px rgba(15, 23, 42, 0.08);
        }}

        * {{
            box-sizing: border-box;
        }}

        body {{
            margin:0;
            font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC";
            background:
                radial-gradient(circle at top left, rgba(96,165,250,0.14), transparent 30%),
                var(--bg);
            padding:24px;
            color:var(--text);
            font-size:16px;
            transition: background 0.2s ease, color 0.2s ease;
        }}

        body.dark {{
            --bg: #0f172a;
            --panel: #162033;
            --panel-soft: #1e293b;
            --text: #e5edf7;
            --muted: #94a3b8;
            --border: #334155;
            --accent: #93c5fd;
            --accent-strong: #c4b5fd;
            --accent-soft: rgba(96,165,250,0.18);
            --button-bg: linear-gradient(135deg,#60a5fa,#a78bfa);
            --button-bg-hover: linear-gradient(135deg,#3b82f6,#8b5cf6);
            --danger: #fb7185;
            --shadow: 0 16px 40px rgba(0, 0, 0, 0.28);
        }}

        .page {{
            max-width:1280px;
            margin:0 auto;
        }}

        .nav {{
            display:flex;
            gap:8px;
            flex-wrap:wrap;
            margin:0 0 18px;
        }}

        .nav-link {{
            min-height:36px;
            padding:8px 12px;
            border-radius:8px;
            background:var(--panel);
            border:1px solid var(--border);
            color:var(--text);
            text-decoration:none;
            font-size:13px;
            font-weight:700;
            display:inline-flex;
            align-items:center;
            justify-content:center;
        }}

        .nav-link.active {{
            color:white;
            background:var(--button-bg);
            border:none;
        }}

        .topbar {{
            display:flex;
            align-items:flex-end;
            justify-content:space-between;
            gap:16px;
            margin-bottom:18px;
        }}

        h2 {{
            margin:0;
            font-size:28px;
            line-height:1.2;
            letter-spacing:0;
        }}

        .subtitle {{
            margin:8px 0 0;
            color:var(--muted);
            font-size:13px;
        }}

        .theme-control {{
            flex:0 0 auto;
            display:flex;
            align-items:center;
            gap:10px;
            padding:8px 10px 8px 14px;
            border-radius:999px;
            border:1px solid var(--border);
            background:var(--panel);
            box-shadow:var(--shadow);
            color:var(--muted);
            font-size:13px;
            font-weight:700;
            cursor:pointer;
            user-select:none;
        }}

        .switch {{
            position:relative;
            width:52px;
            height:30px;
            flex:0 0 auto;
        }}

        .switch input {{
            position:absolute;
            opacity:0;
            width:0;
            height:0;
        }}

        .slider {{
            position:absolute;
            inset:0;
            border-radius:999px;
            background:#cbd5e1;
            transition:background 0.2s ease;
            box-shadow:inset 0 1px 3px rgba(15,23,42,0.18);
        }}

        .slider::before {{
            content:"";
            position:absolute;
            width:26px;
            height:26px;
            left:2px;
            top:2px;
            border-radius:50%;
            background:#ffffff;
            box-shadow:0 2px 8px rgba(15,23,42,0.25);
            transition:transform 0.2s ease;
        }}

        .switch input:checked + .slider {{
            background:linear-gradient(135deg,#60a5fa,#a78bfa);
        }}

        .switch input:checked + .slider::before {{
            transform:translateX(22px);
        }}

        .layout {{
            display:grid;
            grid-template-columns: minmax(280px, 0.82fr) minmax(0, 1.8fr);
            gap:16px;
            align-items:start;
        }}

        .card {{
            background:var(--panel);
            padding:16px;
            border-radius:8px;
            border:1px solid var(--border);
            box-shadow:var(--shadow);
        }}

        .search-card {{
            margin-bottom:16px;
            display:flex;
            gap:10px;
            align-items:center;
        }}

        .tool-row {{
            display:flex;
            gap:10px;
            flex-wrap:wrap;
            margin-bottom:16px;
            align-items:center;
        }}

        .tool-row form {{
            display:flex;
            gap:10px;
            flex:1 1 auto;
            flex-wrap:nowrap;
            align-items:center;
        }}

        .tool-row input[type="file"] {{
            flex:1 1 auto;
            min-width:260px;
            margin-bottom:0;
        }}

        .tool-row .export-link,
        .tool-row button {{
            flex:0 0 auto;
            min-height:40px;
            white-space:nowrap;
            padding:8px 14px;
        }}

        .search-card input {{
            flex:1 1 auto;
            min-width:220px;
            margin-bottom:0;
        }}

        .search-card button,
        .search-card .cancel-link {{
            flex:0 0 auto;
            min-width:86px;
            min-height:40px;
            padding:8px 16px;
            white-space:nowrap;
        }}

        input, textarea {{
            width:100%;
            padding:10px 12px;
            margin-bottom:12px;
            border-radius:8px;
            border:1px solid var(--border);
            background:var(--panel-soft);
            color:var(--text);
            outline:none;
            font:inherit;
            transition:0.2s;
        }}

        input:focus, textarea:focus {{
            border-color:var(--accent);
            background:var(--panel);
        }}

        textarea {{
            min-height:150px;
            resize:vertical;
            line-height:1.6;
        }}

        button {{
            min-height:40px;
            padding:8px 14px;
            border:none;
            border-radius:8px;
            background:var(--button-bg);
            color:white;
            cursor:pointer;
            font-weight:700;
            transition: transform 0.15s ease, background 0.15s ease;
        }}

        button:hover {{
            transform: translateY(-1px);
            background:var(--button-bg-hover);
        }}

        .table-wrap {{
            overflow-x:auto;
            border-radius:8px;
            border:1px solid var(--border);
            background:var(--panel);
        }}

        table {{
            width:100%;
            border-collapse:collapse;
            background:var(--panel);
        }}

        th {{
            text-align:left;
            background:var(--panel-soft);
            padding:12px;
            color:var(--muted);
            font-size:13px;
            white-space:nowrap;
        }}

        td {{
            padding:12px;
            border-top:1px solid var(--border);
            font-size:13px;
            vertical-align:top;
            line-height:1.6;
        }}

        tr:hover {{
            background:var(--panel-soft);
        }}

        .question-cell {{
            width:28%;
            font-weight:700;
        }}

        .answer-cell {{
            color:var(--muted);
            white-space:pre-wrap;
        }}

        .actions {{
            display:flex;
            gap:8px;
            flex-wrap:wrap;
            white-space:nowrap;
        }}

        .btn-edit, .btn-del, .cancel-link, .export-link {{
            min-height:32px;
            padding:7px 30px;
            color:white;
            border-radius:8px;
            text-decoration:none;
            font-size:12px;
            font-weight:700;
            display:inline-flex;
            align-items:center;
            justify-content:center;
            margin:0;
        }}

        .btn-edit {{
            background:var(--button-bg);
        }}

        .btn-del {{
            background:var(--danger);
        }}

        .cancel-link {{
            color:var(--text);
            background:var(--panel-soft);
            border:1px solid var(--border);
        }}

        .export-link {{
            background:var(--accent-soft);
            color:var(--accent);
            border:1px solid rgba(96,165,250,0.35);
        }}

        .top-title {{
            font-weight:700;
            margin-bottom:12px;
            font-size:16px;
        }}

        .form-actions {{
            display:flex;
            gap:8px;
            flex-wrap:wrap;
            align-items:center;
        }}

        @media (max-width: 860px) {{
            body {{
                padding:14px;
            }}

            .topbar {{
                align-items:stretch;
                flex-direction:column;
            }}

            h2 {{
                font-size:24px;
            }}

            .theme-control {{
                width:100%;
                justify-content:space-between;
            }}

            .layout {{
                grid-template-columns:1fr;
            }}

            .search-card {{
                display:grid;
                grid-template-columns:1fr;
            }}

            .tool-row,
            .tool-row form {{
                display:grid;
                grid-template-columns:1fr;
            }}

            .tool-row input[type="file"],
            .tool-row .export-link,
            .tool-row button {{
                width:100%;
                min-width:0;
            }}

            .search-card input,
            .search-card button,
            .search-card .cancel-link {{
                width:100%;
                min-width:0;
            }}

            .table-wrap {{
                overflow:visible;
                background:transparent;
                border:none;
                box-shadow:none;
            }}

            table, tbody, tr, td {{
                display:block;
                width:100%;
            }}

            table {{
                background:transparent;
            }}

            tr:first-child {{
                display:none;
            }}

            tr {{
                margin-bottom:12px;
                border:1px solid var(--border);
                border-radius:8px;
                background:var(--panel);
                box-shadow:var(--shadow);
                overflow:hidden;
            }}

            td {{
                display:grid;
                grid-template-columns:76px 1fr;
                gap:10px;
                border-top:1px solid var(--border);
                padding:10px 12px;
            }}

            td:first-child {{
                border-top:none;
            }}

            td::before {{
                content:attr(data-label);
                color:var(--muted);
                font-weight:700;
            }}

            .question-cell {{
                width:auto;
            }}

            .actions {{
                display:grid;
                grid-template-columns:repeat(2, minmax(0, 1fr));
                gap:10px;
                white-space:normal;
            }}

            .actions::before {{
                grid-column:1 / -1;
            }}

            .actions .btn-edit,
            .actions .btn-del {{
                width:100%;
            }}
        }}
    </style>

    <script>
        (function(){{
            const savedTheme = localStorage.getItem("faq-theme");
            if(savedTheme === "dark"){{
                document.addEventListener("DOMContentLoaded", function(){{
                    document.body.classList.add("dark");
                }});
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
            localStorage.setItem("faq-theme", isDark ? "dark" : "light");
        }}
    </script>
    </head>

    <body>
    <main class="page">

    <header class="topbar">
        <div>
            <h2>FAQ 管理中心</h2>
            <p class="subtitle">管理 LINE 客服優先回答的常見問題</p>
        </div>
        <label class="theme-control">
            <span>深夜模式</span>
            <span class="switch">
                <input id="theme-toggle" type="checkbox" onchange="toggleTheme()">
                <span class="slider"></span>
            </span>
        </label>
    </header>

    <nav class="nav">{nav_html("FAQ")}</nav>

    <form class="card search-card" method="get" action="/faq">
        <input name="q" value="{e(q)}" placeholder="搜尋 FAQ 問題或答案">
        <button>搜尋</button>
        <a href="/faq" class="cancel-link">清空</a>
    </form>

    <div class="card tool-row">
        
        <form method="post" action="/faq/import" enctype="multipart/form-data">
            <input type="file" name="file" accept=".csv" required>
            <button>匯入 FAQ CSV</button>
            <a href="/faq/export" class="export-link">匯出 FAQ CSV</a>
        </form>
    </div>

    <div class="layout">

        <!-- LEFT: FORM -->
        <div class="card">
            <div class="top-title">{form_title}</div>

            <form method="post" action="{e(form_action)}">
                <input name="question" placeholder="問題" value="{e(q_val)}" required>
                <textarea name="answer" placeholder="答案" required>{e(a_val)}</textarea>

                <div class="form-actions">
                    <button>{btn_text}</button>
                    {"<a href='/faq' class='cancel-link'>取消編輯</a>" if is_edit else ""}
                </div>
            </form>
        </div>

        <!-- RIGHT: TABLE -->
        <div class="card">
            <div class="top-title">FAQ 清單</div>
            <div class="table-wrap">
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

    </div>
    </main>

    </body>
    </html>
    """)


# =========================
# ADD
# =========================
@router.post("/faq/add")
def add(
    question: str = Form(...),
    answer: str = Form(...),
    return_to: str = Form("/faq")
):

    faq = load_faq()

    exists = any(
        normalize_question(item.get("question", "")) == normalize_question(question)
        for item in faq
    )

    if not exists:
        faq.append({
            "question": question,
            "answer": answer
        })

        save_faq(faq)

    if not return_to.startswith("/"):
        return_to = "/faq"

    return RedirectResponse(return_to, status_code=302)


@router.get("/faq/export")
def export_faq():
    faq = load_faq()
    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(["question", "answer"])

    for item in faq:
        writer.writerow([item.get("question", ""), item.get("answer", "")])

    filename = f"faq_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )


@router.post("/faq/import")
async def import_faq(file: UploadFile = File(...)):
    content = await file.read()
    text = content.decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(text))
    faq = load_faq()
    questions = {normalize_question(item.get("question", "")) for item in faq}

    if reader.fieldnames and {"question", "answer"}.issubset(set(reader.fieldnames)):
        rows = [(row.get("question", ""), row.get("answer", "")) for row in reader]
    else:
        raw_rows = csv.reader(io.StringIO(text))
        rows = []
        for row in raw_rows:
            if len(row) >= 2:
                rows.append((row[0], row[1]))

    for question, answer in rows:
        question = str(question).strip()
        answer = str(answer).strip()

        if not question or normalize_question(question) in questions:
            continue

        faq.append({"question": question, "answer": answer})
        questions.add(normalize_question(question))

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
