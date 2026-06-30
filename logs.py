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
# SORT KEY MAP
# =========================
SORT_MAP = {
    "id": "id",
    "time": "time",
    "platform": "platform",
    "message": "message",
    "reply": "reply",
    "latency": "latency",
    "ip": "ip",
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
        logs = [
            l for l in logs
            if keyword.lower() in str(l.get("message", "")).lower()
            or keyword.lower() in str(l.get("reply", "")).lower()
        ]

    if user:
        logs = [l for l in logs if l.get("user") == user]

    # =========================
    # SAFE SORT FIELD
    # =========================
    sort_key = SORT_MAP.get(sort_by, "time")
    reverse = (sort_order == "desc")

    def sort_func(x):
        val = x.get(sort_key, "")
        return val

    logs.sort(key=sort_func, reverse=reverse)

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
            <td>{g(l,'time')}</td>
            <td>{g(l,'platform','LINE')}</td>

            <td>{str(g(l,'message'))[:50]}</td>
            <td>{str(g(l,'reply'))[:80]}</td>

            <td>{g(l,'latency','-')}s</td>
            <td>{g(l,'sources','-')}</td>
            <td>{g(l,'ip','-')}</td>

            <td>
                <details>
                    <summary>View</summary>
                    <div style="padding:10px;background:#f9fafb;border-radius:10px;margin-top:8px">
                        <b>SESSION</b><br>{g(l,'session_id','-')}<br><br>

                        <b>MODEL</b><br>{meta.get('model','deepseek')}<br>
                        <b>DEVICE</b><br>{meta.get('device','-')}<br>
                        <b>BROWSER</b><br>{meta.get('browser','-')}<br><br>

                        <b>USER AGENT</b><br>{meta.get('user_agent','-')}<br>
                    </div>
                </details>
            </td>
        </tr>
        """

    # =========================
    # SORT LINKS
    # =========================
    def sort_link(col):
        order = "asc" if sort_order == "desc" else "desc"
        return f"?sort_by={col}&sort_order={order}&page=1&size={size}"

    # =========================
    # PAGINATION LINKS
    # =========================
    pages = ""

    if page > 1:
        pages += f'<a href="?page={page-1}&size={size}&sort_by={sort_by}&sort_order={sort_order}">上一頁</a> '

    for p in range(1, total_pages + 1):
        pages += f'<a href="?page={p}&size={size}&sort_by={sort_by}&sort_order={sort_order}">{p}</a> '

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
            background:#f5f7fb;
        }}

        .wrap {{
            padding:20px;
        }}

        h1 {{
            margin-bottom:10px;
        }}

        /* FILTER */
        .filters {{
            display:flex;
            gap:10px;
            flex-wrap:wrap;
            background:white;
            padding:12px;
            border-radius:12px;
            margin-bottom:15px;
        }}

        input, select {{
            padding:8px;
            border-radius:999px;
            border:1px solid #ddd;
        }}

        /* TABLE */
        table {{
            width:100%;
            border-collapse:collapse;
            background:white;
            border-radius:12px;
            overflow:hidden;
        }}

        th {{
            background:#f3f4f6;
            padding:10px;
            text-align:left;
            cursor:pointer;
            user-select:none;
        }}

        td {{
            padding:10px;
            border-top:1px solid #eee;
            font-size:13px;
        }}

        details summary {{
            cursor:pointer;
            background:#3b82f6;
            color:white;
            padding:4px 8px;
            border-radius:999px;
            font-size:12px;
        }}

        /* PAGINATION */
        .pages a {{
            margin-right:6px;
            padding:4px 10px;
            background:white;
            border:1px solid #ddd;
            border-radius:999px;
            text-decoration:none;
        }}
    </style>
    </head>

    <body>
    <div class="wrap">

    <h1>Logs</h1>

    <form class="filters">
        <input name="keyword" placeholder="關鍵字" value="{keyword}">
        <input name="user" placeholder="User" value="{user}">

        <select name="size">
            <option value="10">10筆</option>
            <option value="20">20筆</option>
            <option value="50">50筆</option>
        </select>

        <select name="sort_by">
            <option value="time">時間</option>
            <option value="platform">平台</option>
            <option value="latency">回應時間</option>
        </select>

        <select name="sort_order">
            <option value="desc">DESC</option>
            <option value="asc">ASC</option>
        </select>

        <button>搜尋</button>
    </form>

    <table>
        <tr>
            <th><a href="{sort_link('id')}">ID</a></th>
            <th><a href="{sort_link('time')}">時間</a></th>
            <th><a href="{sort_link('platform')}">平台</a></th>
            <th>問題</th>
            <th>回覆</th>
            <th><a href="{sort_link('latency')}">回應時間</a></th>
            <th>來源</th>
            <th><a href="{sort_link('ip')}">IP</a></th>
            <th>Detail</th>
        </tr>

        {rows}
    </table>

    <div style="margin-top:15px">
        {pages}
    </div>

    </div>
    </body>
    </html>
    """)