from fastapi import APIRouter
from fastapi.responses import HTMLResponse
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

        rows += f"""
        <tr>
            <td>{g(l,'id', i+1)}</td>
            <td class="time">{g(l,'time')}</td>
            <td><span class="pill">{g(l,'platform','LINE')}</span></td>

            <td class="msg">{str(g(l,'message',''))[:45]}</td>

            <!-- 🔥 限制回覆欄寬（關鍵修正） -->
            <td class="reply-cell">{str(g(l,'reply',''))[:60]}</td>

            <td class="latency">{g(l,'latency','-')}</td>
            <td class="source">{g(l,'source','-')}</td>
            <td class="ip">{g(l,'ip','-')}</td>

            <td>
                <details>
                    <summary>DETAIL</summary>

                    <div class="detail-box">

                        <div class="grid">
                            <div><b>DEVICE</b><br>{meta.get('device','-')}</div>
                            <div><b>BROWSER</b><br>{meta.get('browser','-')}</div>
                            <div><b>USER AGENT</b><br>{meta.get('user_agent','-')}</div>
                        </div>

                        <div class="block">
                            <b>完整問題</b>
                            <div>{g(l,'message','')}</div>
                        </div>

                        <div class="block">
                            <b>完整回覆</b>
                            <div class="reply-box">{g(l,'reply','')}</div>
                        </div>

                    </div>
                </details>
            </td>
        </tr>
        """

    # =========================
    # OPTIONS
    # =========================
    page_opts = [10, 20, 50]

    def link(p):
        return f"?page={p}&size={size}&keyword={keyword}&platform={platform}&source={source}&sort_by={sort_by}&sort_order={sort_order}"

    # =========================
    # PAGE BAR
    # =========================
    pages = ""

    if page > 1:
        pages += f'<a href="{link(page-1)}">← 上一頁</a> '

    pages += f"<span class='info'>第 {page}/{total_pages} 頁 ｜ 總數 {total} ｜ 每頁 {size} 筆</span> "

    if page < total_pages:
        pages += f'<a href="{link(page+1)}">下一頁 →</a>'

    # =========================
    # SIZE OPTIONS
    # =========================
    size_select = "".join(
        [f'<option value="{s}" {"selected" if s==size else ""}>{s} 筆</option>' for s in page_opts]
    )

    # =========================
    # CSS ONLY UPGRADE
    # =========================
    css = """
    body {
        margin:0;
        font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC";
        background: linear-gradient(180deg,#f4f6fb,#eef2ff);
        padding:18px;
        color:#111827;
    }

    h2 {
        margin-bottom:12px;
        font-weight:700;
    }

    /* FILTER BAR */
    .bar {
        background:white;
        padding:14px;
        margin-bottom:14px;
        border-radius:16px;
        display:flex;
        gap:10px;
        flex-wrap:wrap;
        box-shadow:0 8px 20px rgba(0,0,0,0.06);
    }

    input, select {
        padding:8px 12px;
        border-radius:999px;
        border:1px solid #e5e7eb;
        background:#f9fafb;
        outline:none;
        transition:0.2s;
    }

    input:focus, select:focus {
        border-color:#93c5fd;
        background:white;
    }

    button {
        padding:8px 14px;
        border-radius:999px;
        border:none;
        background:linear-gradient(135deg,#60a5fa,#a78bfa);
        color:white;
        cursor:pointer;
        font-weight:600;
    }

    /* TABLE */
    table {
        width:100%;
        border-collapse:collapse;
        background:white;
        border-radius:16px;
        overflow:hidden;
        box-shadow:0 10px 24px rgba(0,0,0,0.06);
    }

    th {
        background:linear-gradient(135deg,#eef2ff,#f8fafc);
        padding:12px;
        text-align:left;
        font-size:13px;
        font-weight:700;
        color:#374151;
    }

    td {
        padding:12px;
        border-top:1px solid #f1f1f1;
        font-size:13px;
        vertical-align:top;
    }

    tr:hover {
        background:#f9fafb;
    }

    .pill {
        padding:4px 10px;
        border-radius:999px;
        background:linear-gradient(135deg,#dbeafe,#e0e7ff);
        font-size:12px;
    }

    .latency {
        color:#16a34a;
        font-weight:700;
    }

    .msg { max-width:160px; }

    /* 🔥 核心修正：回覆欄位縮窄 */
    .reply-cell {
        max-width:180px;
        overflow:hidden;
        text-overflow:ellipsis;
        white-space:nowrap;
        color:#374151;
    }

    .source {
        font-weight:600;
        color:#4f46e5;
    }

    .ip {
        font-family:monospace;
        color:#6b7280;
    }

    details summary {
        cursor:pointer;
        padding:6px 10px;
        border-radius:999px;
        background:linear-gradient(135deg,#3b82f6,#6366f1);
        color:white;
        font-size:12px;
        font-weight:600;
    }

    .detail-box {
        margin-top:10px;
        padding:12px;
        background:#f8fafc;
        border-radius:12px;
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

    .reply-box {
        background:white;
        padding:10px;
        border-radius:10px;
        border:1px solid #e5e7eb;
    }

    .pages {
        margin:12px 0;
        display:flex;
        gap:10px;
        align-items:center;
        flex-wrap:wrap;
        justify-content:center; /* ← 加這行才會置中 */
    }

    .pages a {
        padding:6px 10px;
        border-radius:999px;
        background:white;
        border:1px solid #e5e7eb;
        text-decoration:none;
        color:#374151;
        font-size: 12px;
    }

    .info {
        font-size:13px;
        color:#6b7280;
    }
    """

    return HTMLResponse(f"""
    <html>
    <head>
    <meta charset="utf-8"/>
    </head>

    <body>

    <h2>LOGS DASHBOARD</h2>

    <form class="bar">
        <input name="keyword" placeholder="關鍵字" value="{keyword}">

        <select name="size">
            {size_select}
        </select>

        <select name="sort_by">
            <option value="time">依時間</option>
            <option value="latency">依回應時間</option>
            <option value="source">依來源</option>
        </select>

        <select name="sort_order">
            <option value="desc">降序</option>
            <option value="asc">升序</option>
        </select>

        <a href="/logs" style="padding:8px 14px; border-radius:999px; background:#ef4444; color:white; text-decoration:none; font-weight:600;">清空</a>

        <button>搜尋</button>
    </form>

    <div class="pages">{pages}</div>

    <table>
        <tr>
            <th>ID</th>
            <th>時間</th>
            <th>平台</th>
            <th>問題</th>
            <th>回覆</th>
            <th>延遲</th>
            <th>來源</th>
            <th>IP</th>
            <th>DETAIL</th>
        </tr>

        {rows}
    </table>

    <div class="pages">{pages}</div>

    <style>{css}</style>

    </body>
    </html>
    """)