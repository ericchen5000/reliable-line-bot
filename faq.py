from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
import csv
import html
import io
import json
import os
import zipfile
from datetime import datetime
from urllib.parse import urlencode
from xml.etree import ElementTree
from admin_ui import admin_bar_css, admin_bar_html
import admin_tools

router = APIRouter()

FAQ_PATH = "data/faq.json"
URLS_PATH = "data/urls.json"
KB_DIR = "knowledge/txt"


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


def load_urls():
    if not os.path.exists(URLS_PATH):
        return []
    try:
        with open(URLS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except:
        return []


def save_urls(data):
    os.makedirs(os.path.dirname(URLS_PATH), exist_ok=True)
    with open(URLS_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def current_admin_name(request):
    username = admin_tools.current_admin(request)
    return admin_tools.admin_display_name(username) if username else "管理員"


def audit_text(item):
    updated_by = item.get("updated_by") or item.get("created_by") or "-"
    updated_at = item.get("updated_at") or item.get("created_at") or "-"
    return f"{updated_by}<br><span class='meta-time'>{updated_at}</span>"


def kb_last_activity(filename):
    activities = admin_tools.load_json(admin_tools.ADMIN_ACTIVITY_PATH, [])
    for item in reversed(activities):
        if item.get("target") == filename and str(item.get("action", "")).startswith("KB"):
            return f"{item.get('display') or item.get('admin') or '-'}<br><span class='meta-time'>{item.get('time', '-')}</span>"
    return "-"


def kb_files():
    os.makedirs(KB_DIR, exist_ok=True)
    files = []

    for name in sorted(os.listdir(KB_DIR)):
        path = os.path.join(KB_DIR, name)
        if name.startswith(".") or not os.path.isfile(path) or not name.endswith(".txt"):
            continue
        try:
            size = os.path.getsize(path)
        except:
            size = 0
        files.append({"name": name, "size": size})

    return files


def safe_kb_filename(value):
    name = os.path.basename(str(value or "").strip())
    name = "".join(ch for ch in name if ch.isalnum() or ch in {"-", "_", "."})

    if not name:
        name = "kb"

    if not name.endswith(".txt"):
        name += ".txt"

    return name


def converted_kb_filename(value):
    name = os.path.basename(str(value or "").strip())
    stem = os.path.splitext(name)[0] or "kb"
    stem = "".join(ch for ch in stem if ch.isalnum() or ch in {"-", "_", "."})

    if not stem:
        stem = "kb"

    return stem + ".txt"


def decode_text(content):
    try:
        return content.decode("utf-8-sig")
    except:
        return content.decode("utf-8", errors="ignore")


def xml_text_from_bytes(content):
    root = ElementTree.fromstring(content)
    parts = []

    for node in root.iter():
        if node.text and node.text.strip():
            parts.append(node.text.strip())

    return "\n".join(parts)


def extract_docx_text(content):
    parts = []

    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        names = [
            name for name in archive.namelist()
            if name.startswith("word/") and name.endswith(".xml")
            and (
                name == "word/document.xml"
                or name.startswith("word/header")
                or name.startswith("word/footer")
            )
        ]

        for name in names:
            try:
                text = xml_text_from_bytes(archive.read(name))
                if text:
                    parts.append(text)
            except:
                pass

    return "\n\n".join(parts)


def extract_pptx_text(content):
    slides = []

    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        names = sorted(
            name for name in archive.namelist()
            if name.startswith("ppt/slides/slide") and name.endswith(".xml")
        )

        for index, name in enumerate(names, start=1):
            try:
                text = xml_text_from_bytes(archive.read(name))
                if text:
                    slides.append(f"第 {index} 頁\n{text}")
            except:
                pass

    return "\n\n".join(slides)


def extract_pdf_text(content):
    try:
        from pypdf import PdfReader
    except ImportError:
        raise ValueError("PDF 轉文字需要安裝 pypdf：pip install pypdf")

    reader = PdfReader(io.BytesIO(content))
    pages = []

    for index, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            pages.append(f"第 {index} 頁\n{text.strip()}")

    return "\n\n".join(pages)


def extract_kb_text(filename, content):
    ext = os.path.splitext(str(filename or "").lower())[1]

    if ext == ".txt":
        return decode_text(content)

    if ext == ".docx":
        return extract_docx_text(content)

    if ext == ".pptx":
        return extract_pptx_text(content)

    if ext == ".pdf":
        return extract_pdf_text(content)

    raise ValueError("目前支援 TXT、PDF、DOCX、PPTX")


def kb_notice_url(message):
    return "/faq?" + urlencode({"notice": message}) + "#kb-manager"


def e(value):
    return html.escape(str(value))


def nav_html(active=""):
    items = [
        ("/", "Dashboard"),
        ("/logs", "LOGS"),
        ("/faq", "知識管理"),
        ("/test-chat", "測試"),
        ("/admin/users", "帳號管理"),
    ]
    links = "".join(
        f'<a class="nav-link {"active" if active == label else ""}" href="{href}">{label}</a>'
        for href, label in items
    )
    return f'<button type="button" class="nav-toggle" onclick="this.closest(\'nav\').classList.toggle(\'open\')">☰ 選單</button><div class="nav-menu">{links}</div>'


def normalize_question(value):
    return str(value).strip().lower()


# =========================
# MAIN PAGE (ALL IN ONE)
# =========================
@router.get("/faq", response_class=HTMLResponse)
def faq_page(edit_id: int = None, edit_url: int = None, q: str = "", notice: str = ""):

    faq = load_faq()
    urls = load_urls()
    files = kb_files()
    search_text = q.strip().lower()

    edit_item = None
    if edit_id is not None and 0 <= edit_id < len(faq):
        edit_item = faq[edit_id]

    edit_url_item = None
    if edit_url is not None and 0 <= edit_url < len(urls):
        edit_url_item = urls[edit_url]

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
            <td data-label="最後修改" class="meta-cell">{audit_text(item)}</td>

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

    url_rows = ""
    for i, item in enumerate(urls):
        keywords = ", ".join(item.get("keywords", [])) if isinstance(item.get("keywords"), list) else str(item.get("keywords", ""))
        url_rows += f"""
        <tr>
            <td data-label="網站">{e(item.get('title', '-'))}</td>
            <td data-label="網址">{e(item.get('url', '-'))}</td>
            <td data-label="關鍵字">{e(keywords)}</td>
            <td data-label="最後修改" class="meta-cell">{audit_text(item)}</td>
            <td data-label="操作" class="actions">
                <a href="/faq?edit_url={i}" class="btn-edit">編輯</a>
                <a href="/faq/urls/delete/{i}" class="btn-del" onclick="return confirm('確定要刪除這個網站索引嗎？')">刪除</a>
            </td>
        </tr>
        """

    if not url_rows:
        url_rows = "<tr><td colspan='5'>尚未設定網站索引</td></tr>"

    url_is_edit = edit_url_item is not None
    url_form_action = f"/faq/urls/edit/{edit_url}" if url_is_edit else "/faq/urls/add"
    url_form_title = "編輯網站索引" if url_is_edit else "新增網站索引"
    url_btn_text = "更新網站" if url_is_edit else "新增網站"
    url_title = edit_url_item.get("title", "") if url_is_edit else ""
    url_value = edit_url_item.get("url", "") if url_is_edit else ""
    url_keywords = edit_url_item.get("keywords", []) if url_is_edit else []
    url_keywords_value = ", ".join(url_keywords) if isinstance(url_keywords, list) else str(url_keywords)

    kb_rows = ""
    for item in files:
        name = item.get("name", "")
        kb_rows += f"""
        <tr>
            <td data-label="檔名">{e(name)}</td>
            <td data-label="大小">{e(item.get('size', 0))} bytes</td>
            <td data-label="最後修改" class="meta-cell">{kb_last_activity(name)}</td>
            <td data-label="操作" class="actions">
                <a href="/faq/kb/delete/{e(name)}" class="btn-del" onclick="return confirm('確定要刪除這個 KB 文件嗎？')">刪除</a>
            </td>
        </tr>
        """

    if not kb_rows:
        kb_rows = "<tr><td colspan='4'>尚無 KB 文件</td></tr>"

    return HTMLResponse(f"""
    <html>
    <head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1"/>

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
            min-height:100vh;
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
            margin:0 0 18px;
        }}

        .nav-menu {{
            display:flex;
            gap:8px;
            flex-wrap:wrap;
        }}

        .nav-toggle {{
            display:none;
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
            border:1px solid transparent;
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

        .meta-cell {{
            min-width:110px;
            color:var(--text);
            font-size:13px;
            font-weight:700;
        }}

        .meta-time {{
            color:var(--muted);
            font-size:12px;
            font-weight:600;
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

        .section-tabs {{
            display:flex;
            gap:8px;
            flex-wrap:wrap;
            margin:0 0 16px;
        }}

        .section-tabs a {{
            min-height:34px;
            padding:7px 11px;
            border-radius:999px;
            border:1px solid var(--border);
            background:var(--panel-soft);
            color:var(--muted);
            text-decoration:none;
            font-size:13px;
            font-weight:700;
        }}

        .section-title {{
            margin:22px 0 12px;
        }}

        .section-title h3 {{
            margin:0;
            font-size:20px;
        }}

        .management-grid {{
            display:grid;
            grid-template-columns:minmax(280px, 0.9fr) minmax(0, 1.6fr);
            gap:16px;
            align-items:start;
        }}

        .hint {{
            color:var(--muted);
            font-size:13px;
            line-height:1.6;
            margin:8px 0 0;
        }}

        .notice {{
            margin-bottom:16px;
            color:var(--accent-strong);
            background:var(--accent-soft);
            border-color:rgba(96,165,250,0.35);
            font-weight:700;
        }}

        {admin_bar_css()}

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

            .nav-toggle {{
                display:flex;
                width:100%;
                min-height:40px;
                padding:8px 12px;
                border-radius:8px;
                border:1px solid var(--border);
                background:var(--panel);
                color:var(--text);
                font-weight:700;
                align-items:center;
                justify-content:space-between;
            }}

            .nav-menu {{
                display:none;
                grid-template-columns:1fr;
                gap:8px;
                margin-top:8px;
            }}

            .nav.open .nav-menu {{
                display:grid;
            }}

            .nav-link {{
                width:100%;
            }}

            .layout {{
                grid-template-columns:1fr;
            }}

            .management-grid {{
                grid-template-columns:1fr;
            }}

            .section-tabs {{
                display:grid;
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
                grid-template-columns:76px minmax(0, 1fr);
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
    {admin_bar_html()}
    <main class="page">

    <header class="topbar">
        <div>
            <h2>知識管理中心</h2>
            <p class="subtitle">集中管理 FAQ、網站索引與 KB 文件</p>
        </div>
        <label class="theme-control">
            <span>深夜模式</span>
            <span class="switch">
                <input id="theme-toggle" type="checkbox" onchange="toggleTheme()">
                <span class="slider"></span>
            </span>
        </label>
    </header>

    <nav class="nav">{nav_html("知識管理")}</nav>

    <div class="section-tabs">
        <a href="#faq-manager">FAQ 管理</a>
        <a href="#url-manager">網站索引管理</a>
        <a href="#kb-manager">知識庫文件管理</a>
    </div>

    {f'<div class="card notice">{e(notice)}</div>' if notice else ''}

    <div class="section-title" id="faq-manager">
        <h3>FAQ 管理</h3>
        <p class="subtitle">管理客服優先回答的常見問題。</p>
    </div>
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
                    <th>最後修改</th>
                    <th>操作</th>
                </tr>
                {rows}
            </table>
            </div>
        </div>

    </div>

    <div class="section-title" id="url-manager">
        <h3>網站索引管理</h3>
        <p class="subtitle">新增、編輯或刪除可被 AI 客服搜尋的指定網站。</p>
    </div>
    <div class="management-grid">
        <div class="card">
            <div class="top-title">{url_form_title}</div>
            <form method="post" action="{e(url_form_action)}">
                <input name="title" placeholder="網站名稱，例如：新聞中心" value="{e(url_title)}" required>
                <input name="url" placeholder="網址，例如：https://www.reliable.com.tw/category/pr/" value="{e(url_value)}" required>
                <textarea name="keywords" placeholder="關鍵字，用逗號分隔，例如：新聞, PR, 最新消息">{e(url_keywords_value)}</textarea>
                <div class="form-actions">
                    <button>{url_btn_text}</button>
                    {"<a href='/faq#url-manager' class='cancel-link'>取消編輯</a>" if url_is_edit else ""}
                </div>
                <p class="hint">新增後如果要讓網站索引立即更新，請到 Dashboard 按「立即建立索引」。</p>
            </form>
        </div>
        <div class="card">
            <div class="top-title">網站索引清單</div>
            <div class="table-wrap">
            <table>
                <tr>
                    <th>網站</th>
                    <th>網址</th>
                    <th>關鍵字</th>
                    <th>最後修改</th>
                    <th>操作</th>
                </tr>
                {url_rows}
            </table>
            </div>
        </div>
    </div>

    <div class="section-title" id="kb-manager">
        <h3>知識庫文件管理</h3>
        <p class="subtitle">新增或刪除 KB 文字文件，AI 客服會搜尋 knowledge/txt 裡的 .txt 檔。</p>
    </div>
    <div class="management-grid">
        <div class="card">
            <div class="top-title">新增 KB 文件</div>
            <form method="post" action="/faq/kb/add">
                <input name="filename" placeholder="檔名，例如：array_license.txt" required>
                <textarea name="content" placeholder="輸入 KB 內容" required></textarea>
                <button>新增 KB</button>
            </form>
            <hr style="border:none; border-top:1px solid var(--border); margin:16px 0;">
            <div class="top-title">上傳文件轉 KB</div>
            <form method="post" action="/faq/kb/upload" enctype="multipart/form-data">
                <input type="file" name="file" accept=".txt,.pdf,.docx,.pptx" required>
                <button>上傳並轉成 KB</button>
            </form>
            <p class="hint">支援 TXT、DOCX、PPTX；PDF 需伺服器安裝 pypdf 才能抽文字。</p>
        </div>
        <div class="card">
            <div class="top-title">KB 文件清單</div>
            <div class="table-wrap">
            <table>
                <tr>
                    <th>檔名</th>
                    <th>大小</th>
                    <th>最後修改</th>
                    <th>操作</th>
                </tr>
                {kb_rows}
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
    request: Request,
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
        admin_name = current_admin_name(request)
        now = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        faq.append({
            "question": question,
            "answer": answer,
            "created_by": admin_name,
            "created_at": now,
            "updated_by": admin_name,
            "updated_at": now,
        })

        save_faq(faq)
        admin_tools.log_admin_activity(request, "新增 FAQ", question)

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
async def import_faq(request: Request, file: UploadFile = File(...)):
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

    admin_name = current_admin_name(request)
    now = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
    imported = 0

    for question, answer in rows:
        question = str(question).strip()
        answer = str(answer).strip()

        if not question or normalize_question(question) in questions:
            continue

        faq.append({
            "question": question,
            "answer": answer,
            "created_by": admin_name,
            "created_at": now,
            "updated_by": admin_name,
            "updated_at": now,
        })
        questions.add(normalize_question(question))
        imported += 1

    save_faq(faq)
    admin_tools.log_admin_activity(request, "匯入 FAQ", file.filename or "CSV", f"{imported} 筆")
    return RedirectResponse("/faq", status_code=302)


# =========================
# EDIT
# =========================
@router.post("/faq/edit/{idx}")
def edit(request: Request, idx: int, question: str = Form(...), answer: str = Form(...)):

    faq = load_faq()

    if 0 <= idx < len(faq):
        original = faq[idx]
        admin_name = current_admin_name(request)
        faq[idx] = {
            "question": question,
            "answer": answer,
            "created_by": original.get("created_by", ""),
            "created_at": original.get("created_at", ""),
            "updated_by": admin_name,
            "updated_at": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
        }
        admin_tools.log_admin_activity(request, "編輯 FAQ", question)

    save_faq(faq)

    return RedirectResponse("/faq", status_code=302)


# =========================
# DELETE
# =========================
@router.get("/faq/delete/{idx}")
def delete(request: Request, idx: int):

    faq = load_faq()

    if 0 <= idx < len(faq):
        removed = faq.pop(idx)
        admin_tools.log_admin_activity(request, "刪除 FAQ", removed.get("question", f"#{idx + 1}"))

    save_faq(faq)

    return RedirectResponse("/faq", status_code=302)


def parse_keywords(value):
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


@router.post("/faq/urls/add")
def add_url(
    request: Request,
    title: str = Form(...),
    url: str = Form(...),
    keywords: str = Form("")
):
    urls = load_urls()
    url = url.strip()

    if url and not any(item.get("url") == url for item in urls):
        admin_name = current_admin_name(request)
        now = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        urls.append({
            "title": title.strip(),
            "url": url,
            "keywords": parse_keywords(keywords),
            "created_by": admin_name,
            "created_at": now,
            "updated_by": admin_name,
            "updated_at": now,
        })
        save_urls(urls)
        admin_tools.log_admin_activity(request, "新增網站索引", url)

    return RedirectResponse("/faq#url-manager", status_code=302)


@router.post("/faq/urls/edit/{idx}")
def edit_url(
    request: Request,
    idx: int,
    title: str = Form(...),
    url: str = Form(...),
    keywords: str = Form("")
):
    urls = load_urls()

    if 0 <= idx < len(urls):
        original = urls[idx]
        admin_name = current_admin_name(request)
        urls[idx] = {
            "title": title.strip(),
            "url": url.strip(),
            "keywords": parse_keywords(keywords),
            "created_by": original.get("created_by", ""),
            "created_at": original.get("created_at", ""),
            "updated_by": admin_name,
            "updated_at": datetime.now().strftime("%Y/%m/%d %H:%M:%S"),
        }
        save_urls(urls)
        admin_tools.log_admin_activity(request, "編輯網站索引", url.strip())

    return RedirectResponse("/faq#url-manager", status_code=302)


@router.get("/faq/urls/delete/{idx}")
def delete_url(request: Request, idx: int):
    urls = load_urls()

    if 0 <= idx < len(urls):
        removed = urls.pop(idx)
        save_urls(urls)
        admin_tools.log_admin_activity(request, "刪除網站索引", removed.get("url", f"#{idx + 1}"))

    return RedirectResponse("/faq#url-manager", status_code=302)


@router.post("/faq/kb/add")
def add_kb(
    request: Request,
    filename: str = Form(...),
    content: str = Form(...)
):
    os.makedirs(KB_DIR, exist_ok=True)
    name = safe_kb_filename(filename)
    path = os.path.join(KB_DIR, name)

    with open(path, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")
    admin_tools.log_admin_activity(request, "KB 新增", name)

    return RedirectResponse("/faq#kb-manager", status_code=302)


@router.post("/faq/kb/upload")
async def upload_kb(request: Request, file: UploadFile = File(...)):
    os.makedirs(KB_DIR, exist_ok=True)
    name = converted_kb_filename(file.filename)
    content = await file.read()

    try:
        text = extract_kb_text(file.filename, content)
    except Exception as exc:
        return RedirectResponse(kb_notice_url(str(exc)), status_code=302)

    if not text.strip():
        return RedirectResponse(kb_notice_url("轉換後沒有可讀取的文字內容"), status_code=302)

    with open(os.path.join(KB_DIR, name), "w", encoding="utf-8") as f:
        f.write(text.strip() + "\n")
    admin_tools.log_admin_activity(request, "KB 上傳", name, file.filename or "")

    return RedirectResponse(kb_notice_url(f"已轉成 KB：{name}"), status_code=302)


@router.get("/faq/kb/delete/{filename}")
def delete_kb(request: Request, filename: str):
    name = safe_kb_filename(filename)
    path = os.path.join(KB_DIR, name)

    if os.path.exists(path) and os.path.isfile(path):
        os.remove(path)
        admin_tools.log_admin_activity(request, "KB 刪除", name)

    return RedirectResponse("/faq#kb-manager", status_code=302)
