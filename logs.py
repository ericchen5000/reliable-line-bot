from fastapi import APIRouter
from fastapi.responses import HTMLResponse
import json
import os

router = APIRouter()

LOG_PATH = "logs/chat_logs.json"


# =========================
# LOAD LOGS
# =========================
def load_logs():
    if not os.path.exists(LOG_PATH):
        return []

    try:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


# =========================
# SAFE GET
# =========================
def g(d, key, default="-"):
    return d.get(key, default) if isinstance(d, dict) else default


# =========================
# SHORT TIME
# =========================
def short_time(t):
    if not t:
        return "-"
    try:
        return str(t)[11:19]
    except:
        return str(t)


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
    sort_by: str = "time",
    sort_order: str = "desc",
    keyword: str = "",
    user: str = ""
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

    if user:
        logs = [l for l in logs if l.get("user") == user]

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
    # ROWS (DETAIL BUTTON ONLY)
    # =========================
    rows = ""

    for i, l in enumerate(logs_page):
        meta = l.get("meta", {}) if isinstance(l.get("meta"), dict) else {}

        rows += f"""
        <tr>
            <td>{g(l,'id', i+1)}</td>
            <td class="time">{short_time(g(l,'time'))}</td>
            <td><span class="pill">{g(l,'platform','LINE')}</span></td>

            <td class="msg">{str(g(l,'message'))[:45]}</td>
            <td class="reply">{str(g(l,'reply'))[:70]}</td>

            <td class="latency">{g(l,'latency','-')}s</td>
            <td>{g(l,'source','-')}</td>
            <td>{g(l,'ip','-')}</td>

            <td>
                <details class="detail-box">
                    <summary>DETAIL</summary>

                    <div class="detail">

                        <div class="grid">
                            <div><b>來源</b><br>{g(l,'source','-')}</div>
                            <div><b>IP</b><br>{g(l,'ip','-')}</div>
                            <div><b>SESSION</b><br>{g(l,'session_id','-')}</div>
                            <div><b>DEVICE</b><br>{meta.get('device','-')}</div>
                            <div><b>BROWSER</b><br>{meta.get('browser','-')}</div>
                            <div><b>USER AGENT</b><br>{meta.get('user_agent','-')}</div>
                        </div>

                        <div class="block">
                            <b>完整問題</b><br>{g(l,'message','')}
                        </div>

                        <div class="block">
                            <b>完整回覆</b><br>{g(l,'reply','')}
                        </div>

                    </div>
                </details>
            </td>
        </tr>
        """

    # =========================
    # PAGINATION
    # =========================
    pages = ""

    if page > 1:
        pages += f'<a href="?page={page-1}&size={size}&sort_by={sort_by}&sort_order={sort_order}">上一頁</a> '

    pages += f"<span> 第 {page}/{total_pages} 頁 ｜ 總 {total} 筆 ｜ 每頁 {size} 筆 </span> "

    if page < total_pages:
        pages += f'<a href="?page={page+1}&size={size}&sort_by={sort_by}&sort_order={sort_order}">下一頁</a>'

    # =========================
    # HTML
    # =========================
    return HTMLResponse(f"""
    <html>
    <head>
    <meta charset="utf-8"/>

    <style>
        body {{
            margin:0;
            font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC";
            background:#f4f6fb;
            padding:18px;
        }}

        table {{
            width:100%;
            border-collapse:collapse;
            background:white;
            border-radius:14px;
            overflow:hidden;
        }}

        th {{
            background:#eef2ff;
            padding:10px;
            text-align:left;
        }}

        td {{
            padding:10px;
            border-top:1px solid #eee;
            font-size:13px;
            vertical-align:top;
        }}

        .pill {{
            padding:4px 10px;
            border-radius:999px;
            background:#dbeafe;
            font-size:12px;
        }}

        .latency {{
            color:#16a34a;
            font-weight:bold;
        }}

        .msg {{
            max-width:160px;
        }}

        .reply {{
            max-width:220px;
            color:#374151;
        }}

        .time {{
            font-size:12px;
            color:#6b7280;
        }}

        details summary {{
            cursor:pointer;
            background:#3b82f6;
            color:white;
            padding:5px 10px;
            border-radius:999px;
            font-size:12px;
        }}

        .detail {{
            margin-top:10px;
            padding:12px;
            background:#f9fafb;
            border-radius:12px;
            font-size:13px;
        }}

        .grid {{
            display:grid;
            grid-template-columns:repeat(3, 1fr);
            gap:10px;
            margin-bottom:10px;
            font-size:12px;
        }}

        .block {{
            margin-top:10px;
        }}

        a {{
            margin:0 5px;
            text-decoration:none;
        }}

        .topbar {{
            margin-bottom:10px;
        }}
    </style>
    </head>

    <body>

    <h2>LOGS</h2>

    <div class="topbar">
        {pages}
    </div>

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

    <div class="topbar">
        {pages}
    </div>

    </body>
    </html>
    """)