from fastapi import APIRouter, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response
import csv
import html
import io
import json
import os
import re
import zipfile
from datetime import datetime
from urllib.parse import quote, urlencode
from xml.etree import ElementTree
from admin_ui import admin_bar_css, admin_bar_html
import admin_tools

router = APIRouter()

FAQ_PATH = "data/faq.json"
URLS_PATH = "data/urls.json"
KB_DIR = "knowledge/txt"
KB_DISABLED_DIR = "knowledge/txt_disabled"


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


def is_active_item(item):
    return item.get("active", True) is not False


def status_badge(active):
    label = "啟用" if active else "停用"
    css = "status-on" if active else "status-off"
    return f"<span class='status-pill {css}'>{label}</span>"


def redirect_with_notice(url, message):
    if not str(url or "").startswith("/"):
        url = "/faq"

    base, marker, fragment = str(url).partition("#")
    sep = "&" if "?" in base else "?"
    next_url = f"{base}{sep}{urlencode({'notice': message})}"

    if marker:
        next_url += f"#{fragment}"

    return RedirectResponse(next_url, status_code=302)


def kb_last_activity(filename):
    activities = admin_tools.load_json(admin_tools.ADMIN_ACTIVITY_PATH, [])
    for item in reversed(activities):
        if item.get("target") == filename and str(item.get("action", "")).startswith("KB"):
            return f"{item.get('display') or item.get('admin') or '-'}<br><span class='meta-time'>{item.get('time', '-')}</span>"
    return "-"


def kb_files():
    os.makedirs(KB_DIR, exist_ok=True)
    os.makedirs(KB_DISABLED_DIR, exist_ok=True)
    files = []

    for base_dir, active in [(KB_DIR, True), (KB_DISABLED_DIR, False)]:
        for name in sorted(os.listdir(base_dir)):
            path = os.path.join(base_dir, name)
            if name.startswith(".") or not os.path.isfile(path) or not name.endswith(".txt"):
                continue
            try:
                size = os.path.getsize(path)
            except:
                size = 0
            files.append({"name": name, "size": size, "active": active})

    return files


def kb_path(filename, active=True):
    base_dir = KB_DIR if active else KB_DISABLED_DIR
    return os.path.join(base_dir, safe_kb_filename(filename))


def read_kb_file(filename, active=True):
    path = kb_path(filename, active)

    if not os.path.exists(path) or not os.path.isfile(path):
        return ""

    try:
        with open(path, "r", encoding="utf-8-sig") as f:
            return f.read()
    except:
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()


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


def clean_extracted_text(value):
    text = str(value or "")
    text = text.replace("\x00", "")
    text = re.sub(r"[\x01-\x08\x0b\x0c\x0e-\x1f]", "", text)
    lines = []

    for line in text.splitlines():
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line:
            lines.append(line)

    return "\n".join(lines)


def local_name(tag):
    return str(tag).rsplit("}", 1)[-1]


def xml_text_from_bytes(content, allowed_tags=None):
    root = ElementTree.fromstring(content)
    parts = []

    for node in root.iter():
        if allowed_tags and local_name(node.tag) not in allowed_tags:
            continue
        if node.text and node.text.strip():
            parts.append(node.text.strip())

    return clean_extracted_text("\n".join(parts))


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
                text = xml_text_from_bytes(archive.read(name), {"t"})
                if text:
                    parts.append(text)
            except:
                pass

    return "\n\n".join(parts)


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

    if ext == ".pdf":
        return extract_pdf_text(content)

    raise ValueError("目前支援 TXT、PDF、DOCX")


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
def faq_page(
    request: Request,
    edit_id: int = None,
    edit_url: int = None,
    edit_kb: str = "",
    kb_active: int = 1,
    q: str = "",
    notice: str = ""
):

    faq = load_faq()
    urls = load_urls()
    files = kb_files()
    search_text = q.strip().lower()
    readonly = admin_tools.is_readonly_admin(request)

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

        active = is_active_item(item)
        edit_query = urlencode({"edit_id": i, "q": q}) if q else urlencode({"edit_id": i})
        action_html = (
            '<span class="readonly-pill">唯讀</span>'
            if readonly else
            f"""
                <a href="/faq?{e(edit_query)}" class="btn-edit">編輯</a>
                <a href="/faq/toggle/{i}" class="btn-toggle {'toggle-off' if active else 'toggle-on'}">{'停用' if active else '啟用'}</a>
                <a href="/faq/delete/{i}" class="btn-del" onclick="return confirm('確定要永久刪除這筆 FAQ 嗎？此動作無法復原。')">刪除</a>
            """
        )

        rows += f"""
        <tr>
            <td data-label="ID">{i+1}</td>
            <td data-label="狀態">{status_badge(active)}</td>
            <td data-label="問題" class="question-cell">{e(item.get('question',''))}</td>
            <td data-label="答案" class="answer-cell">{e(item.get('answer',''))}</td>
            <td data-label="最後修改" class="meta-cell">{audit_text(item)}</td>

            <td data-label="操作" class="actions">
                {action_html}
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
        active = is_active_item(item)
        url_action_html = (
            '<span class="readonly-pill">唯讀</span>'
            if readonly else
            f"""
                <a href="/faq?edit_url={i}" class="btn-edit">編輯</a>
                <a href="/faq/urls/toggle/{i}" class="btn-toggle {'toggle-off' if active else 'toggle-on'}">{'停用' if active else '啟用'}</a>
                <a href="/faq/urls/delete/{i}" class="btn-del" onclick="return confirm('確定要永久刪除這個網站索引嗎？此動作無法復原。')">刪除</a>
            """
        )
        url_rows += f"""
        <tr>
            <td data-label="狀態">{status_badge(active)}</td>
            <td data-label="網站">{e(item.get('title', '-'))}</td>
            <td data-label="網址">{e(item.get('url', '-'))}</td>
            <td data-label="關鍵字">{e(keywords)}</td>
            <td data-label="最後修改" class="meta-cell">{audit_text(item)}</td>
            <td data-label="操作" class="actions">
                {url_action_html}
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
    kb_edit_name = safe_kb_filename(edit_kb) if edit_kb else ""
    kb_edit_active = bool(kb_active)
    kb_edit_content = read_kb_file(kb_edit_name, kb_edit_active) if kb_edit_name else ""
    kb_is_edit = bool(kb_edit_name and os.path.exists(kb_path(kb_edit_name, kb_edit_active)))
    kb_form_title = f"編輯 KB 文件：{kb_edit_name}" if kb_is_edit else "新增 KB 文件"

    kb_rows = ""
    for item in files:
        name = item.get("name", "")
        active = item.get("active", True)
        encoded_name = quote(name)
        kb_action_html = (
            '<span class="readonly-pill">唯讀</span>'
            if readonly else
            f'''
                <a href="/faq?edit_kb={encoded_name}&kb_active={"1" if active else "0"}#kb-manager" class="btn-edit">編輯</a>
                <a href="/faq/kb/toggle/{encoded_name}?active={"1" if active else "0"}" class="btn-toggle {"toggle-off" if active else "toggle-on"}">{"停用" if active else "啟用"}</a>
                <a href="/faq/kb/delete/{encoded_name}?active={"1" if active else "0"}" class="btn-del" onclick="return confirm('確定要永久刪除這個 KB 文件嗎？此動作無法復原。')">刪除</a>
            '''
        )
        kb_rows += f"""
        <tr>
            <td data-label="狀態">{status_badge(active)}</td>
            <td data-label="檔名">{e(name)}</td>
            <td data-label="大小">{e(item.get('size', 0))} bytes</td>
            <td data-label="最後修改" class="meta-cell">{kb_last_activity(name)}</td>
            <td data-label="操作" class="actions">
                {kb_action_html}
            </td>
        </tr>
        """

    if not kb_rows:
        kb_rows = "<tr><td colspan='4'>尚無 KB 文件</td></tr>"

    readonly_card = """
        <div class="card readonly-panel">
            <div class="top-title">唯讀模式</div>
            <p class="hint">目前帳號只能查看資料，不能新增、編輯、停用、啟用、匯入或上傳。</p>
        </div>
    """

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
            --warning: #d97706;
            --success: #16a34a;
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
            --warning: #fbbf24;
            --success: #4ade80;
            --shadow: 0 16px 40px rgba(0, 0, 0, 0.28);
        }}

        .page {{
            max-width:1400px;
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
            display:grid;
            grid-template-columns:repeat(auto-fit, 72px);
            gap:8px;
            align-items:center;
            justify-content:start;
            white-space:normal;
        }}

        .btn-edit, .btn-del, .btn-toggle, .cancel-link, .export-link {{
            min-height:32px;
            padding:7px 14px;
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

        .actions .btn-edit,
        .actions .btn-del,
        .actions .btn-toggle {{
            width:72px;
            padding-left:0;
            padding-right:0;
        }}

        .btn-edit {{
            background:var(--button-bg);
        }}

        .btn-del {{
            background:var(--danger);
        }}

        .btn-toggle {{
            background:var(--warning);
        }}

        .btn-toggle.toggle-on {{
            background:var(--success);
        }}

        .status-pill {{
            min-height:28px;
            padding:5px 10px;
            border-radius:999px;
            font-size:12px;
            font-weight:900;
            display:inline-flex;
            align-items:center;
            justify-content:center;
            border:1px solid transparent;
            white-space:nowrap;
        }}

        .status-on {{
            color:#15803d;
            background:#dcfce7;
            border-color:#bbf7d0;
        }}

        .status-off {{
            color:#92400e;
            background:#fef3c7;
            border-color:#fde68a;
        }}

        .readonly-pill {{
            min-height:32px;
            padding:7px 12px;
            border-radius:8px;
            background:var(--panel-soft);
            border:1px solid var(--border);
            color:var(--muted);
            font-size:12px;
            font-weight:800;
            display:inline-flex;
            align-items:center;
            justify-content:center;
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

        .readonly-panel {{
            background:linear-gradient(135deg, rgba(96,165,250,0.10), rgba(167,139,250,0.10)), var(--panel);
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
            .actions .btn-del,
            .actions .btn-toggle {{
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

    {'' if readonly else f'''
    <div class="card tool-row">
        
        <form method="post" action="/faq/import" enctype="multipart/form-data">
            <input type="file" name="file" accept=".csv" required>
            <button>匯入 FAQ CSV</button>
            <a href="/faq/export" class="export-link">匯出 FAQ CSV</a>
        </form>
    </div>
    '''}

    <div class="layout">

        <!-- LEFT: FORM -->
        {readonly_card if readonly else f'''
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
        '''}

        <!-- RIGHT: TABLE -->
        <div class="card">
            <div class="top-title">FAQ 清單</div>
            <div class="table-wrap">
            <table>
                <tr>
                    <th>ID</th>
                    <th>狀態</th>
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
        {readonly_card if readonly else f'''
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
        '''}
        <div class="card">
            <div class="top-title">網站索引清單</div>
            <div class="table-wrap">
            <table>
                <tr>
                    <th>狀態</th>
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
        {readonly_card if readonly else f'''
        <div class="card">
            <div class="top-title">{e(kb_form_title)}</div>
            <form method="post" action="{f'/faq/kb/edit/{quote(kb_edit_name)}?active={1 if kb_edit_active else 0}' if kb_is_edit else '/faq/kb/add'}">
                <input name="filename" placeholder="檔名，例如：array_license.txt" value="{e(kb_edit_name)}" {"readonly" if kb_is_edit else ""} required>
                <textarea name="content" placeholder="輸入 KB 內容" required>{e(kb_edit_content) if kb_is_edit else ""}</textarea>
                <div class="form-actions">
                    <button>{'儲存 KB' if kb_is_edit else '新增 KB'}</button>
                    {"<a href='/faq#kb-manager' class='cancel-link'>取消編輯</a>" if kb_is_edit else ""}
                </div>
            </form>
            <hr style="border:none; border-top:1px solid var(--border); margin:16px 0;">
            <div class="top-title">上傳文件轉 KB</div>
            <form method="post" action="/faq/kb/upload" enctype="multipart/form-data">
                <input type="file" name="file" accept=".txt,.pdf,.docx" required>
                <button>上傳並轉成 KB</button>
            </form>
            <p class="hint">支援 TXT、DOCX、PDF。系統會抽出文字後另存成 knowledge/txt 裡的 .txt。</p>
        </div>
        '''}
        <div class="card">
            <div class="top-title">KB 文件清單</div>
            <div class="table-wrap">
            <table>
                <tr>
                    <th>狀態</th>
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
            "active": True,
        })

        save_faq(faq)
        admin_tools.log_admin_activity(request, "新增 FAQ", question)
        notice = "FAQ 已新增"
    else:
        notice = "FAQ 已存在，未重複新增"

    if not return_to.startswith("/"):
        return_to = "/faq"

    return redirect_with_notice(return_to, notice)


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
            "active": True,
        })
        questions.add(normalize_question(question))
        imported += 1

    save_faq(faq)
    admin_tools.log_admin_activity(request, "匯入 FAQ", file.filename or "CSV", f"{imported} 筆")
    return redirect_with_notice("/faq", f"FAQ 匯入完成，共新增 {imported} 筆")


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
            "active": original.get("active", True),
        }
        admin_tools.log_admin_activity(request, "編輯 FAQ", question)

    save_faq(faq)

    return redirect_with_notice("/faq", "FAQ 已更新")


@router.get("/faq/toggle/{idx}")
def toggle_faq(request: Request, idx: int):
    faq = load_faq()

    if 0 <= idx < len(faq):
        item = faq[idx]
        next_active = not is_active_item(item)
        item["active"] = next_active
        item["updated_by"] = current_admin_name(request)
        item["updated_at"] = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        save_faq(faq)
        action = "啟用 FAQ" if next_active else "停用 FAQ"
        admin_tools.log_admin_activity(request, action, item.get("question", f"#{idx + 1}"))
        return redirect_with_notice("/faq", f"FAQ 已{'啟用' if next_active else '停用'}")

    return redirect_with_notice("/faq", "找不到指定 FAQ")


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
        return redirect_with_notice("/faq", "FAQ 已刪除")

    return redirect_with_notice("/faq", "找不到指定 FAQ")


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
            "active": True,
        })
        save_urls(urls)
        admin_tools.log_admin_activity(request, "新增網站索引", url)
        return redirect_with_notice("/faq#url-manager", "網站索引已新增")

    return redirect_with_notice("/faq#url-manager", "網站索引已存在，未重複新增")


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
            "active": original.get("active", True),
        }
        save_urls(urls)
        admin_tools.log_admin_activity(request, "編輯網站索引", url.strip())

    return redirect_with_notice("/faq#url-manager", "網站索引已更新")


@router.get("/faq/urls/toggle/{idx}")
def toggle_url(request: Request, idx: int):
    urls = load_urls()

    if 0 <= idx < len(urls):
        item = urls[idx]
        next_active = not is_active_item(item)
        item["active"] = next_active
        item["updated_by"] = current_admin_name(request)
        item["updated_at"] = datetime.now().strftime("%Y/%m/%d %H:%M:%S")
        save_urls(urls)
        action = "啟用網站索引" if next_active else "停用網站索引"
        admin_tools.log_admin_activity(request, action, item.get("url", f"#{idx + 1}"))
        return redirect_with_notice("/faq#url-manager", f"網站索引已{'啟用' if next_active else '停用'}")

    return redirect_with_notice("/faq#url-manager", "找不到指定網站索引")


@router.get("/faq/urls/delete/{idx}")
def delete_url(request: Request, idx: int):
    urls = load_urls()

    if 0 <= idx < len(urls):
        removed = urls.pop(idx)
        save_urls(urls)
        admin_tools.log_admin_activity(request, "刪除網站索引", removed.get("url", f"#{idx + 1}"))
        return redirect_with_notice("/faq#url-manager", "網站索引已刪除")

    return redirect_with_notice("/faq#url-manager", "找不到指定網站索引")


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

    return redirect_with_notice("/faq#kb-manager", "KB 已新增")


@router.post("/faq/kb/edit/{filename}")
def edit_kb(
    request: Request,
    filename: str,
    active: int = 1,
    content: str = Form(...)
):
    name = safe_kb_filename(filename)
    path = kb_path(name, bool(active))

    if not os.path.exists(path) or not os.path.isfile(path):
        return redirect_with_notice("/faq#kb-manager", "找不到指定 KB 文件")

    with open(path, "w", encoding="utf-8") as f:
        f.write(content.strip() + "\n")

    admin_tools.log_admin_activity(request, "KB 編輯", name)
    return redirect_with_notice("/faq#kb-manager", "KB 已更新")


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

    return RedirectResponse(kb_notice_url(f"KB 已上傳並轉換完成：knowledge/txt/{name}"), status_code=302)


@router.get("/faq/kb/toggle/{filename}")
def toggle_kb(request: Request, filename: str, active: int = 1):
    name = safe_kb_filename(filename)
    source_dir = KB_DIR if active else KB_DISABLED_DIR
    target_dir = KB_DISABLED_DIR if active else KB_DIR
    source_path = os.path.join(source_dir, name)
    target_path = os.path.join(target_dir, name)

    os.makedirs(target_dir, exist_ok=True)

    if os.path.exists(source_path) and os.path.isfile(source_path):
        if os.path.exists(target_path):
            os.remove(target_path)
        os.rename(source_path, target_path)
        action = "KB 停用" if active else "KB 啟用"
        admin_tools.log_admin_activity(request, action, name)
        return redirect_with_notice("/faq#kb-manager", f"KB 已{'停用' if active else '啟用'}")

    return redirect_with_notice("/faq#kb-manager", "找不到指定 KB 文件")


@router.get("/faq/kb/delete/{filename}")
def delete_kb(request: Request, filename: str, active: int = 1):
    name = safe_kb_filename(filename)
    source_dir = KB_DIR if active else KB_DISABLED_DIR
    path = os.path.join(source_dir, name)

    if os.path.exists(path) and os.path.isfile(path):
        os.remove(path)
        admin_tools.log_admin_activity(request, "KB 刪除", name)
        return redirect_with_notice("/faq#kb-manager", "KB 已刪除")

    return redirect_with_notice("/faq#kb-manager", "找不到指定 KB 文件")
