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
# UI
# =========================
@router.get("/logs", response_class=HTMLResponse)
def logs_ui(
    page: int = 1,
    size: int = 10,
    keyword: str = "",
    channel: str = "",
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

    if channel:
        logs = [l for l in logs if l.get("platform", "LINE") == channel]

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
    # STATS TEXT
    # =========================
    stats = f"第 {page} / {total_pages} 頁 ｜ 總筆數 {total} ｜ 每頁 {size} 筆"

    # =========================
    # ROWS
    # =========================
    rows = ""

    for i, l in enumerate(logs_page):
        meta = l.get("meta", {}) if isinstance(l.get("meta"), dict) else {}

        session_id = g(l, "session_id")
        response_time = g(l, "response_time", "-")
        sources = g(l, "sources")
        ip = g(l, "ip")
        platform = g(l, "platform", "LINE")

        model = g(meta, "model")
        device = g(meta, "device")
        browser = g(meta, "browser")
        ua = g(meta, "user_agent")

        rows += f"""
        <tr>
            <td>{g(l,'id', i+1)}</td>
            <td>{g(l,'time')}</td>
            <td><span class="pill">{platform}</span></td>
            <td>{str(g(l,'message'))[:50]}</td>
            <td>{str(g(l,'reply'))[:80]}</td>
            <td class="rt">{response_time}s</td>
            <td class="src">{sources}</td>
            <td>{ip}</td>

            <td>
                <details>
                    <summary class="btn-mini">查看</summary>

                    <div class="box">
                        <div><b>SESSION ID</b><br>{session_id}</div>

                        <div class="grid">
                            <div><b>回應時間</b><br>{response_time}s</div>
                            <div><b>平台</b><br>{platform}</div>
                            <div><b>設備</b><br>{device}</div>
                            <div><b>瀏覽器</b><br>{browser}</div>
                        </div>

                        <div class="ua">
                            <b>User Agent</b><br>{ua}
                        </div>

                        <div class="full">
                            <b>完整問題</b><br>{g(l,'message')}<br><br>
                            <b>完整回覆</b><br>{g(l,'reply')}
                        </div>
                    </div>

                </details>
            </td>
        </tr>
        """

    # =========================
    # PAGINATION UI
    # =========================
    pages_html = ""

    if page > 1:
        pages_html += f'<a class="page" href="?page={page-1}&size={size}">上一頁</a>'

    for p in range(1, total_pages + 1):
        active = "active" if p == page else ""
        pages_html += f'<a class="page {active}" href="?page={p}&size={size}">{p}</a>'

    if page < total_pages:
        pages_html += f'<a class="page" href="?page={page+1}&size={size}">下一頁</a>'

    # =========================
    # HTML
    # =========================
    html = f"""
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
            margin:0 0 10px 0;
        }}

        .stats {{
            margin:10px 0 18px 0;
            color:#6b7280;
            font-size:13px;
        }}

        /* TABLE */
        table {{
            width:100%;
            border-collapse:collapse;
            background:white;
            border-radius:16px;
            overflow:hidden;
            box-shadow:0 8px 24px rgba(0,0,0,0.06);
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

        /* PILL */
        .pill {{
            padding:4px 10px;
            border-radius:999px;
            background:#dcfce7;
            font-size:12px;
        }}

        /* BUTTON */
        .btn-mini {{
            padding:4px 10px;
            border-radius:999px;
            background:linear-gradient(135deg,#3b82f6,#8b5cf6);
            color:white;
            cursor:pointer;
            font-size:12px;
        }}

        details {{
            cursor:pointer;
        }}

        .box {{
            margin-top:10px;
            background:#f9fafb;
            padding:12px;
            border-radius:12px;
        }}

        .grid {{
            display:grid;
            grid-template-columns:repeat(2,1fr);
            gap:10px;
            margin:10px 0;
        }}

        .rt {{
            font-weight:700;
            color:#16a34a;
        }}

        .pages {{
            margin-top:15px;
        }}

        .page {{
            display:inline-block;
            padding:6px 12px;
            border-radius:999px;
            background:white;
            margin-right:6px;
            text-decoration:none;
            border:1px solid #e5e7eb;
            font-size:12px;
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
            {pages_html}
        </div>

    </div>
    </body>
    </html>
    """

    return HTMLResponse(html)