from fastapi import APIRouter, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response
import csv
import html
import io
import json
import os
from datetime import datetime, time
from urllib.parse import urlencode

router = APIRouter()

LOG_PATH = "logs/chat_logs.json"
FAQ_PATH = "data/faq.json"


# =========================
# LOAD
# =========================
def load_logs():
    if not os.path.exists(LOG_PATH):
        return []

    try:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except:
        return []


def save_logs(data):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def g(d, k, default="-"):
    return d.get(k, default) if isinstance(d, dict) else default


def e(value):
    return html.escape(str(value))


def nav_html(active=""):
    items = [
        ("/", "Dashboard"),
        ("/logs", "LOGS"),
        ("/faq", "FAQ"),
        ("/site-index", "網站索引"),
        ("/test-chat", "測試"),
        ("/health", "健康檢查"),
    ]
    return "".join(
        f'<a class="nav-link {"active" if active == label else ""}" href="{href}">{label}</a>'
        for href, label in items
    )


def load_faq_questions():
    if not os.path.exists(FAQ_PATH):
        return set()

    try:
        with open(FAQ_PATH, "r", encoding="utf-8") as f:
            faq = json.load(f)
    except:
        return set()

    return {
        str(item.get("question", "")).strip().lower()
        for item in faq
        if item.get("question")
    }


# =========================
# SORT MAP
# =========================
SORT_MAP = {
    "id": "id",
    "time": "time",
    "platform": "platform",
    "latency": "latency",
    "ip": "ip",
    "source": "source",
}


def parse_log_time(value):
    try:
        return datetime.strptime(str(value), "%Y/%m/%d %H:%M:%S")
    except:
        return None


def parse_date(value, end_of_day=False):
    if not value:
        return None

    try:
        date_value = datetime.strptime(value, "%Y-%m-%d").date()
        return datetime.combine(date_value, time.max if end_of_day else time.min)
    except:
        return None


def filter_logs(
    logs,
    keyword="",
    platform="",
    source="",
    date_from="",
    date_to="",
    sort_by="time",
    sort_order="desc"
):
    if not isinstance(logs, list):
        logs = []

    if keyword:
        k = keyword.lower()
        logs = [
            l for l in logs
            if k in str(l.get("message", "")).lower()
            or k in str(l.get("reply", "")).lower()
            or k in str(l.get("source", "")).lower()
        ]

    if platform:
        logs = [l for l in logs if l.get("platform") == platform]

    if source:
        logs = [l for l in logs if l.get("source") == source]

    start_at = parse_date(date_from)
    end_at = parse_date(date_to, end_of_day=True)

    if start_at or end_at:
        filtered = []

        for item in logs:
            log_time = parse_log_time(item.get("time", ""))

            if not log_time:
                continue

            if start_at and log_time < start_at:
                continue

            if end_at and log_time > end_at:
                continue

            filtered.append(item)

        logs = filtered

    sort_key = SORT_MAP.get(sort_by, "time")
    reverse = (sort_order == "desc")

    logs.sort(key=lambda x: x.get(sort_key, ""), reverse=reverse)
    return logs


def export_link(
    keyword="",
    platform="",
    source="",
    date_from="",
    date_to="",
    sort_by="time",
    sort_order="desc"
):
    params = {
        "keyword": keyword,
        "platform": platform,
        "source": source,
        "date_from": date_from,
        "date_to": date_to,
        "sort_by": sort_by,
        "sort_order": sort_order,
    }
    query = urlencode({k: v for k, v in params.items() if v})
    return "/logs/export" + (f"?{query}" if query else "")


@router.get("/logs/export")
def export_logs(
    keyword: str = "",
    platform: str = "",
    source: str = "",
    date_from: str = "",
    date_to: str = "",
    sort_by: str = "time",
    sort_order: str = "desc"
):
    logs = filter_logs(load_logs(), keyword, platform, source, date_from, date_to, sort_by, sort_order)

    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(["ID", "時間", "平台", "問題", "回覆", "延遲", "來源", "IP"])

    for i, item in enumerate(logs):
        writer.writerow([
            g(item, "id", i + 1),
            g(item, "time"),
            g(item, "platform", "LINE"),
            g(item, "message", ""),
            g(item, "reply", ""),
            g(item, "latency", "-"),
            g(item, "source", "-"),
            g(item, "ip", "-"),
        ])

    filename = f"chat_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.post("/logs/quality/{log_id}")
def mark_quality(
    log_id: int,
    quality: str = Form(...),
    return_to: str = Form("/logs")
):
    allowed = {"good", "fix", "wrong"}
    logs = load_logs()

    if quality in allowed:
        for item in logs:
            if item.get("id") == log_id:
                item["quality"] = quality
                break
        save_logs(logs)

    if not return_to.startswith("/"):
        return_to = "/logs"

    return RedirectResponse(return_to, status_code=302)


# =========================
# UI
# =========================
@router.get("/logs", response_class=HTMLResponse)
def logs_ui(
    page: int = 1,
    size: int = 10,
    keyword: str = "",
    platform: str = "",
    source: str = "",
    date_from: str = "",
    date_to: str = "",
    sort_by: str = "time",
    sort_order: str = "desc"
):

    logs = filter_logs(load_logs(), keyword, platform, source, date_from, date_to, sort_by, sort_order)

    # =========================
    # PAGINATION
    # =========================
    total = len(logs)
    total_pages = max(1, (total + size - 1) // size)

    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages

    start = (page - 1) * size
    end = start + size
    logs_page = logs[start:end]
    current_query = urlencode({
        "page": page,
        "size": size,
        "keyword": keyword,
        "platform": platform,
        "source": source,
        "date_from": date_from,
        "date_to": date_to,
        "sort_by": sort_by,
        "sort_order": sort_order,
    })
    current_return_to = "/logs" + (f"?{current_query}" if current_query else "")

    # =========================
    # ROWS
    # =========================
    rows = ""
    faq_questions = load_faq_questions()

    for i, l in enumerate(logs_page):
        meta = l.get("meta", {}) if isinstance(l.get("meta"), dict) else {}
        message = g(l, "message", "")
        reply = g(l, "reply", "")
        log_id = g(l, "id", i + 1)
        quality = g(l, "quality", "")
        quality_text = {
            "good": "良好",
            "fix": "待修",
            "wrong": "錯誤",
        }.get(quality, "未標記")
        is_faq = str(message).strip().lower() in faq_questions
        transfer_html = '<span class="faq-added-pill">已轉 FAQ</span>' if is_faq else f"""
                <form class="inline-form" method="post" action="/faq/add">
                    <input type="hidden" name="question" value="{e(message)}">
                    <input type="hidden" name="answer" value="{e(reply)}">
                    <input type="hidden" name="return_to" value="{e(current_return_to)}">
                    <button type="submit" class="faq-transfer-btn">轉 FAQ</button>
                </form>
        """

        # =========================
        # MAIN ROW
        # =========================
        rows += f"""
        <tr>
            <td data-label="ID">{e(log_id)}</td>
            <td data-label="時間" class="time">{e(g(l,'time'))}</td>
            <td data-label="平台"><span class="pill">{e(g(l,'platform','LINE'))}</span></td>

            <td data-label="問題" class="msg">{e(str(message)[:45])}</td>
            <td data-label="回覆" class="reply-cell">{e(str(reply)[:60])}</td>

            <td data-label="延遲" class="latency">{e(g(l,'latency','-'))}</td>
            <td data-label="來源" class="source">{e(g(l,'source','-'))}</td>
            <td data-label="IP" class="ip">{e(g(l,'ip','-'))}</td>

            <td data-label="更多資訊" class="log-actions">
                <button onclick="toggleDetail({i})">點擊查看</button>
                {transfer_html}
            </td>
        </tr>

        """

        # =========================
        # DETAIL ROW（在下一列）
        # =========================
        rows += f"""
        <tr id="detail-{i}" class="detail-row" style="display:none;">
            <td colspan="9">
                <div class="detail-box" id="detail-content-{i}">

                    <div class="grid">
                        <!-- 
                        <div><span class="pill-more"><b>DEVICE</b></span><br>{meta.get('device','-')}</div>
                        <div><span class="pill-more"><b>BROWSER</b></span><br>{meta.get('browser','-')}</div>
                        <div><span class="pill-more"><b>USER AGENT</b></span><br>{meta.get('user_agent','-')}</div>
                        <div><span class="pill-more"><b>來源</b></span><br>{g(l,'source','-')}</div>
                        <div><span class="pill-more"><b>IP</b></span><br>{g(l,'ip','-')}</div>
                        -->
                    </div>

                    <div class="block">
                        <span class="pill-more"><b>問題</b></span>
                        <div class="detail-text">{e(message)}</div>
                    </div>

                    <div class="block">
                        <span class="pill-more"><b>回覆</b></span>
                        <div class="detail-text">{e(reply)}</div>
                    </div>

                    <div class="block">
                        <span class="pill-more"><b>品質</b></span>
                        <div class="quality-row">
                            <span class="quality-pill">{e(quality_text)}</span>
                            <form method="post" action="/logs/quality/{e(log_id)}">
                                <input type="hidden" name="return_to" value="{e(current_return_to)}">
                                <button name="quality" value="good">良好</button>
                                <button name="quality" value="fix" class="quality-warn">待修</button>
                                <button name="quality" value="wrong" class="quality-danger">錯誤</button>
                            </form>
                        </div>
                    </div>

                </div>
            </td>
        </tr>
        """

    # =========================
    # OPTIONS
    # =========================
    page_opts = [10, 20, 50]

    def link(p):
        return f"?page={p}&size={size}&keyword={keyword}&platform={platform}&source={source}&date_from={date_from}&date_to={date_to}&sort_by={sort_by}&sort_order={sort_order}"

    pages = ""

    if page > 1:
        pages += f'<a href="{link(page-1)}">← 上一頁</a> '

    pages += f"<span class='info'>第 {page}/{total_pages} 頁 ｜ 總數 {total} ｜ 每頁 {size} 筆</span> "

    if page < total_pages:
        pages += f'<a href="{link(page+1)}">下一頁 →</a>'

    size_select = "".join(
        [f'<option value="{s}" {"selected" if s==size else ""}>{s} 筆</option>' for s in page_opts]
    )
    download_url = export_link(keyword, platform, source, date_from, date_to, sort_by, sort_order)

    # =========================
    # JS（只新增，不動架構）
    # =========================
    js = """
    <script>
    (function(){
        const savedTheme = localStorage.getItem("logs-theme");
        if(savedTheme === "dark"){
            document.body.classList.add("dark");
        }
    })();

    document.addEventListener("DOMContentLoaded", function(){
        const toggle = document.getElementById("theme-toggle");
        if(toggle){
            toggle.checked = document.body.classList.contains("dark");
        }
    });

    function toggleTheme(){
        const toggle = document.getElementById("theme-toggle");
        const isDark = toggle ? toggle.checked : !document.body.classList.contains("dark");
        document.body.classList.toggle("dark", isDark);
        localStorage.setItem("logs-theme", isDark ? "dark" : "light");
    }

    function toggleDetail(i){
        const content = document.getElementById("detail-content-" + i);
        const modal = document.getElementById("detail-modal");
        const body = document.getElementById("detail-modal-body");
        if(!content || !modal || !body) return;
        body.innerHTML = content.innerHTML;
        modal.style.display = "flex";
    }

    function closeModal(){
        const modal = document.getElementById("detail-modal");
        if(modal) modal.style.display = "none";
    }
    </script>
    """

    # =========================
    # CSS（完全不動，只補一點點）
    # =========================
    css = """
    :root {
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
    }

    * {
        box-sizing: border-box;
    }

    body {
        margin:0;
        font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC";
        background:
            radial-gradient(circle at top left, rgba(20,184,166,0.14), transparent 30%),
            var(--bg);
        padding:24px;
        color:var(--text);
        font-size:16px;
        transition: background 0.2s ease, color 0.2s ease;
    }

    body.dark {
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
    }

    .page {
        max-width: 1280px;
        margin: 0 auto;
    }

    .nav {
        display:flex;
        gap:8px;
        flex-wrap:wrap;
        margin:0 0 18px;
    }

    .nav-link {
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
    }

    .nav-link.active {
        color:white;
        background:var(--button-bg);
        border:none;
    }

    .topbar {
        display:flex;
        align-items:flex-end;
        justify-content:space-between;
        gap:16px;
        margin-bottom:18px;
    }

    .title-block h2 {
        margin:0;
        font-size:28px;
        line-height:1.2;
        font-weight:700;
        letter-spacing:0;
    }

    .subtitle {
        margin:8px 0 0;
        color:var(--muted);
        font-size:13px;
    }

    .theme-control {
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
    }

    .switch {
        position:relative;
        width:52px;
        height:30px;
        flex:0 0 auto;
    }

    .switch input {
        position:absolute;
        opacity:0;
        width:0;
        height:0;
    }

    .slider {
        position:absolute;
        inset:0;
        border-radius:999px;
        background:#cbd5e1;
        transition:background 0.2s ease;
        box-shadow:inset 0 1px 3px rgba(15,23,42,0.18);
    }

    .slider::before {
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
    }

    .switch input:checked + .slider {
        background:linear-gradient(135deg,#60a5fa,#a78bfa);
    }

    .switch input:checked + .slider::before {
        transform:translateX(22px);
    }

    .switch input:focus-visible + .slider {
        outline:3px solid rgba(96,165,250,0.35);
        outline-offset:2px;
    }

    /* FILTER BAR */
    .bar {
        background:var(--panel);
        padding:16px;
        margin-bottom:16px;
        border-radius:8px;
        display:flex;
        gap:10px;
        flex-wrap:wrap;
        box-shadow:var(--shadow);
        border:1px solid var(--border);
    }

    input, select {
        min-height:40px;
        padding:8px 12px;
        border-radius:8px;
        border:1px solid var(--border);
        background:var(--panel-soft);
        color:var(--text);
        outline:none;
        transition:0.2s;
        font-size:13px;
    }

    input {
        min-width:240px;
        flex:1 1 260px;
    }

    input[type="date"] {
        min-width:150px;
        flex:0 1 170px;
    }

    input:focus, select:focus {
        border-color:var(--accent);
        background:var(--panel);
    }

    button, .clear-link, .export-link {
        min-height:40px;
        padding:8px 14px;
        border-radius:8px;
        border:none;
        background:var(--button-bg);
        color:white;
        cursor:pointer;
        font-weight:600;
        font-size:13px;
        text-decoration:none;
        display:inline-flex;
        align-items:center;
        justify-content:center;
        transition: transform 0.15s ease, background 0.15s ease;
    }

    button:hover, .clear-link:hover, .export-link:hover {
        transform: translateY(-1px);
        background:var(--button-bg-hover);
    }

    .clear-link {
        background:var(--danger);
    }

    .export-link {
        color:var(--accent);
        background:var(--accent-soft);
        border:1px solid rgba(96,165,250,0.35);
    }

    .export-link:hover {
        color:white;
    }

    .inline-form {
        display:inline-flex;
        margin:0 0 0 6px;
    }

    .inline-form input {
        display:none;
    }

    .faq-transfer-btn {
        background:var(--accent-soft);
        color:var(--accent);
        border:1px solid rgba(96,165,250,0.35);
    }

    .faq-transfer-btn:hover {
        color:white;
        background:var(--button-bg-hover);
    }

    .faq-added-pill {
        min-height:36px;
        padding:7px 10px;
        border-radius:8px;
        display:inline-flex;
        align-items:center;
        justify-content:center;
        color:var(--accent-strong);
        background:var(--accent-soft);
        border:1px solid rgba(96,165,250,0.35);
        font-size:13px;
        font-weight:700;
        white-space:nowrap;
    }

    .log-actions {
        min-width:190px;
        display:flex;
        align-items:center;
        gap:8px;
        white-space:nowrap;
    }

    .log-actions .inline-form {
        margin:0;
    }

    .log-actions > button,
    .log-actions .inline-form button,
    .log-actions .faq-added-pill {
        min-width:82px;
        min-height:36px;
        padding:7px 10px;
        white-space:nowrap;
    }

    /* TABLE */
    .table-wrap {
        overflow-x:auto;
        border-radius:8px;
        box-shadow:var(--shadow);
        border:1px solid var(--border);
        background:var(--panel);
    }

    table {
        width:100%;
        border-collapse:collapse;
        background:var(--panel);
        overflow:hidden;
    }

    th {
        background:var(--panel-soft);
        padding:12px;
        text-align:left;
        font-size:13px;
        font-weight:700;
        color:var(--muted);
        white-space:nowrap;
    }

    td {
        padding:12px;
        border-top:1px solid var(--border);
        font-size:13px;
        vertical-align:top;
        color:var(--text);
    }

    tr:hover {
        background:var(--panel-soft);
    }

    .pill {
        padding:4px 10px;
        border-radius:999px;
        background:var(--accent-soft);
        color:var(--accent-strong);
        font-size:12px;
        font-weight:700;
    }
    
    .pill-more {
        padding:4px 10px;
        border-radius:999px;
        border: 1px solid var(--border);
        color:var(--muted);
        background:var(--panel);
    }

    .latency {
        color:var(--accent-strong);
        font-weight:700;
    }

    .msg {
        max-width:180px;
        line-height:1.5;
    }

    .reply-cell {
        max-width:220px;
        overflow:hidden;
        text-overflow:ellipsis;
        white-space:nowrap;
        color:var(--muted);
    }

    .source {
        font-weight:600;
        color:var(--accent-strong);
        word-break:break-word;
    }

    .ip {
        font-family:monospace;
        color:var(--muted);
    }

    .detail-box {
        margin:8px 0;
        padding:16px;
        background:var(--panel-soft);
        border-radius:8px;
        border:1px solid var(--border);
    }

    .grid {
        display:grid;
        grid-template-columns:repeat(3,1fr);
        gap:10px;
        font-size:12px;
        margin-bottom:10px;
    }

    .block {
        margin-top:10px;
        font-size:13px;
    }

    .detail-text {
        margin:12px 0 0 0;
        padding:12px;
        border-radius:8px;
        background:var(--panel);
        border:1px solid var(--border);
        line-height:1.7;
        white-space:pre-wrap;
    }

    .quality-row {
        display:flex;
        gap:10px;
        flex-wrap:wrap;
        align-items:center;
        margin-top:12px;
    }

    .quality-row form {
        display:flex;
        gap:8px;
        flex-wrap:wrap;
    }

    .quality-row button {
        min-height:34px;
        padding:7px 10px;
    }

    .quality-pill {
        min-height:34px;
        padding:7px 10px;
        border-radius:8px;
        display:inline-flex;
        align-items:center;
        background:var(--panel);
        border:1px solid var(--border);
        color:var(--muted);
        font-weight:700;
    }

    .quality-warn {
        background:#f59e0b;
    }

    .quality-danger {
        background:var(--danger);
    }

    .modal {
        position:fixed;
        inset:0;
        z-index:50;
        display:none;
        align-items:center;
        justify-content:center;
        padding:18px;
        background:rgba(15,23,42,0.55);
    }

    .modal-panel {
        width:min(760px, 100%);
        max-height:88vh;
        overflow:auto;
        background:var(--panel);
        border:1px solid var(--border);
        border-radius:8px;
        box-shadow:var(--shadow);
        padding:16px;
    }

    .modal-head {
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:12px;
        margin-bottom:12px;
    }

    .modal-head h3 {
        margin:0;
    }

    .pages {
        margin:14px 0;
        display:flex;
        gap:10px;
        align-items:center;
        flex-wrap:wrap;
        justify-content:center;
    }

    .pages a {
        padding:8px 12px;
        border-radius:8px;
        background:var(--panel);
        border:1px solid var(--border);
        text-decoration:none;
        color:var(--text);
        font-size: 12px;
    }

    .info {
        font-size:13px;
        color:var(--muted);
    }

    @media (max-width: 760px) {
        body {
            padding:14px;
        }

        .topbar {
            align-items:stretch;
            flex-direction:column;
        }

        .title-block h2 {
            font-size:24px;
        }

        .theme-control {
            width:100%;
            justify-content:space-between;
        }

        .bar {
            display:grid;
            grid-template-columns:1fr;
        }

        input, select, button, .clear-link, .export-link {
            width:100%;
            min-width:0;
        }

        .table-wrap {
            overflow:visible;
            background:transparent;
            border:none;
            box-shadow:none;
        }

        table, tbody, tr, td {
            display:block;
            width:100%;
        }

        table {
            background:transparent;
        }

        tr:first-child {
            display:none;
        }

        tr {
            margin-bottom:12px;
            border:1px solid var(--border);
            border-radius:8px;
            background:var(--panel);
            box-shadow:var(--shadow);
            overflow:hidden;
        }

        tr.detail-row {
            margin-top:-12px;
            border-top:none;
            border-radius:0 0 8px 8px;
            box-shadow:none;
        }

        td {
            display:grid;
            grid-template-columns:92px 1fr;
            gap:10px;
            border-top:1px solid var(--border);
            padding:10px 12px;
        }

        td:first-child {
            border-top:none;
        }

        td::before {
            content:attr(data-label);
            color:var(--muted);
            font-weight:700;
        }

        .log-actions {
            display:grid;
            grid-template-columns:repeat(2, minmax(0, 1fr));
            gap:10px;
            min-width:0;
            align-items:stretch;
        }

        .log-actions::before {
            grid-column:1 / -1;
        }

        .log-actions > button,
        .log-actions .inline-form,
        .log-actions .inline-form button,
        .log-actions .faq-added-pill {
            width:100%;
            min-width:0;
        }

        .log-actions .inline-form {
            display:flex;
            margin:0;
        }

        .detail-row td {
            display:block;
        }

        .detail-row td::before {
            display:none;
        }

        .msg, .reply-cell {
            max-width:none;
            white-space:normal;
            overflow:visible;
            text-overflow:clip;
        }
    }
    """

    return HTMLResponse(f"""
    <html>
    <head>
    <meta charset="utf-8"/>
    </head>

    <body>
    <main class="page">

    <header class="topbar">
        <div class="title-block">
            <h2>LOGS管理介面</h2>
            <p class="subtitle">LINE 對話紀錄、來源與回應時間</p>
        </div>
        <label class="theme-control">
            <span>深夜模式</span>
            <span class="switch">
                <input id="theme-toggle" type="checkbox" onchange="toggleTheme()">
                <span class="slider"></span>
            </span>
        </label>
    </header>

    <nav class="nav">{nav_html("LOGS")}</nav>

    <form class="bar">
        <input name="keyword" value="{e(keyword)}" placeholder="關鍵字">
        <input type="date" name="date_from" value="{e(date_from)}" title="開始日期">
        <input type="date" name="date_to" value="{e(date_to)}" title="結束日期">

        <select name="size">
            {size_select}
        </select>

        <select name="sort_by">
            <option value="time">時間</option>
            <option value="latency">回應時間</option>
            <option value="source">來源</option>
        </select>

        <select name="sort_order">
            <option value="desc">DESC</option>
            <option value="asc">ASC</option>
        </select>

        <a href="/logs" class="clear-link">清空</a>
        <a href="{e(download_url)}" class="export-link">匯出 CSV</a>
        
        <button>搜尋</button>
    </form>

    <div class="pages">{pages}</div>

    <div class="table-wrap">
    <table>
        <tr>
            <th width="3%">ID</th>
            <th width="12%">時間</th>
            <th width="5%">平台</th>
            <th width="14%">問題</th>
            <th width="14%">回覆</th>
            <th width="5%">延遲</th>
            <th width="8%">來源</th>
            <th width="8%">IP</th>
            <th width="5%">更多資訊</th>
        </tr>

        {rows}
    </table>
    </div>

    <div class="pages">{pages}</div>
    </main>

    <div class="modal" id="detail-modal" onclick="if(event.target.id === 'detail-modal') closeModal()">
        <div class="modal-panel">
            <div class="modal-head">
                <h3>對話詳情</h3>
                <button type="button" onclick="closeModal()">關閉</button>
            </div>
            <div id="detail-modal-body"></div>
        </div>
    </div>

    {js}

    <style>{css}</style>

    </body>
    </html>
    """)
