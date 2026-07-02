from fastapi import APIRouter
from fastapi.responses import HTMLResponse
import html
import json
import os

router = APIRouter()

LOG_PATH = "logs/chat_logs.json"


# =========================
# LOAD
# =========================
def load_logs():
    if not os.path.exists(LOG_PATH):
        return []
    try:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def g(d, k, default="-"):
    return d.get(k, default) if isinstance(d, dict) else default


def e(value):
    return html.escape(str(value))


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
    sort_by: str = "time",
    sort_order: str = "desc"
):

    logs = load_logs()

    # =========================
    # FILTER
    # =========================
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

    # =========================
    # SORT
    # =========================
    sort_key = SORT_MAP.get(sort_by, "time")
    reverse = (sort_order == "desc")

    logs.sort(key=lambda x: x.get(sort_key, ""), reverse=reverse)

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

    # =========================
    # ROWS
    # =========================
    rows = ""

    for i, l in enumerate(logs_page):
        meta = l.get("meta", {}) if isinstance(l.get("meta"), dict) else {}

        # =========================
        # MAIN ROW
        # =========================
        rows += f"""
        <tr>
            <td data-label="ID">{e(g(l,'id', i+1))}</td>
            <td data-label="時間" class="time">{e(g(l,'time'))}</td>
            <td data-label="平台"><span class="pill">{e(g(l,'platform','LINE'))}</span></td>

            <td data-label="問題" class="msg">{e(str(g(l,'message',''))[:45])}</td>
            <td data-label="回覆" class="reply-cell">{e(str(g(l,'reply',''))[:60])}</td>

            <td data-label="延遲" class="latency">{e(g(l,'latency','-'))}</td>
            <td data-label="來源" class="source">{e(g(l,'source','-'))}</td>
            <td data-label="IP" class="ip">{e(g(l,'ip','-'))}</td>

            <td data-label="更多資訊">
                <button onclick="toggleDetail({i})">點擊查看</button>
            </td>
        </tr>

        """

        # =========================
        # DETAIL ROW（在下一列）
        # =========================
        rows += f"""
        <tr id="detail-{i}" class="detail-row" style="display:none;">
            <td colspan="9">
                <div class="detail-box">

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
                        <div class="detail-text">{e(g(l,'message',''))}</div>
                    </div>

                    <div class="block">
                        <span class="pill-more"><b>回覆</b></span>
                        <div class="detail-text">{e(g(l,'reply',''))}</div>
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
        return f"?page={p}&size={size}&keyword={keyword}&platform={platform}&source={source}&sort_by={sort_by}&sort_order={sort_order}"

    pages = ""

    if page > 1:
        pages += f'<a href="{link(page-1)}">← 上一頁</a> '

    pages += f"<span class='info'>第 {page}/{total_pages} 頁 ｜ 總數 {total} ｜ 每頁 {size} 筆</span> "

    if page < total_pages:
        pages += f'<a href="{link(page+1)}">下一頁 →</a>'

    size_select = "".join(
        [f'<option value="{s}" {"selected" if s==size else ""}>{s} 筆</option>' for s in page_opts]
    )

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
        const btn = document.getElementById("theme-toggle");
        if(btn){
            btn.textContent = document.body.classList.contains("dark") ? "淺色模式" : "深夜模式";
        }
    });

    function toggleTheme(){
        document.body.classList.toggle("dark");
        const isDark = document.body.classList.contains("dark");
        localStorage.setItem("logs-theme", isDark ? "dark" : "light");
        const btn = document.getElementById("theme-toggle");
        if(btn) btn.textContent = isDark ? "淺色模式" : "深夜模式";
    }

    function toggleDetail(i){
        const el = document.getElementById("detail-" + i);
        if(!el) return;
        el.style.display = (el.style.display === "none") ? "" : "none";
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

    .theme-btn {
        flex:0 0 auto;
        background:var(--panel);
        color:var(--text);
        border:1px solid var(--border);
        box-shadow:none;
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

    input:focus, select:focus {
        border-color:var(--accent);
        background:var(--panel);
    }

    button, .clear-link {
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

    button:hover, .clear-link:hover {
        transform: translateY(-1px);
        background:var(--button-bg-hover);
    }

    .clear-link {
        background:var(--danger);
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

        .theme-btn {
            width:100%;
        }

        .bar {
            display:grid;
            grid-template-columns:1fr;
        }

        input, select, button, .clear-link {
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
        <button id="theme-toggle" class="theme-btn" type="button" onclick="toggleTheme()">深夜模式</button>
    </header>

    <form class="bar">
        <input name="keyword" value="{e(keyword)}" placeholder="關鍵字">

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

    {js}

    <style>{css}</style>

    </body>
    </html>
    """)
