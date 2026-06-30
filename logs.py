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
# MAIN UI
# =========================
@router.get("/logs", response_class=HTMLResponse)
def logs_ui(
    page: int = 1,
    size: int = 10,
    keyword: str = "",
    user: str = "",
    sort: str = "desc"
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
    # SORT
    # =========================
    logs.sort(key=lambda x: x.get("time", ""), reverse=(sort == "desc"))

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
    # STATS
    # =========================
    stats = f"第 {page} / {total_pages} 頁 ｜ 總筆數 {total} ｜ 每頁 {size} 筆"

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
            <td><span class="pill">{g(l,'platform','LINE')}</span></td>

            <td>{str(g(l,'message'))[:50]}</td>
            <td>{str(g(l,'reply'))[:80]}</td>

            <td class="rt">{g(l,'latency','-')}s</td>
            <td>{g(l,'sources','-')}</td>
            <td>{g(l,'ip','-')}</td>

            <td>
                <details>
                    <summary>View</summary>

                    <div class="detail">

                        <b>SESSION ID</b><br>
                        {g(l,'session_id','-')}<br><br>

                        <b>完整問題</b><br>
                        {g(l,'message','')}<br><br>

                        <b>完整回覆</b><br>
                        {g(l,'reply','')}<br><br>

                        <div class="grid">
                            <div><b>平台</b><br>{g(l,'platform','LINE')}</div>
                            <div><b>回應時間</b><br>{g(l,'latency','-')}s</div>
                            <div><b>設備</b><br>{meta.get('device','-')}</div>
                            <div><b>瀏覽器</b><br>{meta.get('browser','-')}</div>
                        </div>

                        <br>
                        <b>User Agent</b><br>
                        {meta.get('user_agent','-')}

                    </div>
                </details>
            </td>
        </tr>
        """

    # =========================
    # PAGINATION UI
    # =========================
    pages = ""

    if page > 1:
        pages += f'<a class="page" href="?page={page-1}&size={size}">上一頁</a>'

    for p in range(1, total_pages + 1):
        pages += f'<a class="page {"active" if p==page else ""}" href="?page={p}&size={size}">{p}</a>'

    if page < total_pages:
        pages += f'<a class="page" href="?page={page+1}&size={size}">下一頁</a>'

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
            color:#111827;
        }}

        .wrap {{
            padding:24px;
        }}

        h1 {{
            margin:0 0 8px 0;
        }}

        .stats {{
            font-size:13px;
            color:#6b7280;
            margin-bottom:15px;
        }}

        /* FILTER */
        .filters {{
            display:flex;
            gap:10px;
            flex-wrap:wrap;
            background:white;
            padding:14px;
            border-radius:16px;
            box-shadow:0 6px 20px rgba(0,0,0,0.06);
            margin-bottom:15px;
        }}

        input {{
            padding:10px;
            border-radius:999px;
            border:1px solid #e5e7eb;
        }}

        button {{
            padding:10px 16px;
            border-radius:999px;
            border:none;
            background:linear-gradient(135deg,#3b82f6,#8b5cf6);
            color:white;
        }}

        /* TABLE */
        table {{
            width:100%;
            border-collapse:collapse;
            background:white;
            border-radius:16px;
            overflow:hidden;
        }}

        th {{
            background:#f3f4f6;
            text-align:left;
            padding:12px;
            font-size:13px;
        }}

        td {{
            padding:12px;
            border-top:1px solid #eee;
            font-size:13px;
            vertical-align:top;
        }}

        .pill {{
            padding:4px 10px;
            border-radius:999px;
            background:#dcfce7;
            font-size:12px;
        }}

        .rt {{
            color:#16a34a;
            font-weight:700;
        }}

        details summary {{
            cursor:pointer;
            padding:4px 10px;
            border-radius:999px;
            background:#3b82f6;
            color:white;
            display:inline-block;
        }}

        .detail {{
            margin-top:10px;
            padding:12px;
            background:#f9fafb;
            border-radius:12px;
        }}

        .grid {{
            display:grid;
            grid-template-columns:repeat(2,1fr);
            gap:10px;
            margin-top:10px;
        }}

        /* PAGINATION */
        .pages {{
            margin-top:15px;
        }}

        .page {{
            display:inline-block;
            padding:6px 12px;
            border-radius:999px;
            background:white;
            margin-right:6px;
            border:1px solid #e5e7eb;
            text-decoration:none;
        }}

        .active {{
            background:#3b82f6;
            color:white;
        }}
    </style>

    </head>

    <body>
    <div class="wrap">

    <h1>AI Chat Logs</h1>
    <div class="stats">{stats}</div>

    <form class="filters">
        <input name="keyword" placeholder="關鍵字">
        <input name="user" placeholder="使用者ID">
        <button>搜尋</button>
    </form>

    <table>
        <tr>
            <th>ID</th>
            <th>時間</th>
            <th>平台</th>
            <th>問題</th>
            <th>回覆</th>
            <th>回應時間</th>
            <th>來源</th>
            <th>IP</th>
            <th>Detail</th>
        </tr>

        {rows}
    </table>

    <div class="pages">
        {pages}
    </div>

    </div>
    </body>
    </html>
    """)