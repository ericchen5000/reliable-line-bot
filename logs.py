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
# FILTER HELPERS
# =========================
def match(log, key, value):
    if not value:
        return True
    return str(log.get(key, "")).lower() == value.lower()


# =========================
# UI
# =========================
@router.get("/logs", response_class=HTMLResponse)
def logs_ui(
    page: int = 1,
    size: int = 10,
    keyword: str = "",
    channel: str = "",
    model: str = "",
    device: str = "",
    browser: str = "",
    sort_by: str = "time",
    sort_order: str = "desc"
):

    logs = load_logs()

    # =========================
    # FILTER
    # =========================
    if keyword:
        logs = [
            l for l in logs
            if keyword.lower() in l.get("message", "").lower()
            or keyword.lower() in l.get("reply", "").lower()
        ]

    logs = [l for l in logs if match(l, "channel", channel)]
    logs = [l for l in logs if l.get("meta", {}).get("model", "") == model or not model]
    logs = [l for l in logs if l.get("meta", {}).get("device", "") == device or not device]
    logs = [l for l in logs if l.get("meta", {}).get("browser", "") == browser or not browser]

    # =========================
    # SORT
    # =========================
    reverse = sort_order == "desc"
    logs.sort(key=lambda x: x.get(sort_by, ""), reverse=reverse)

    # =========================
    # PAGINATION
    # =========================
    total = len(logs)
    start = (page - 1) * size
    end = start + size
    logs_page = logs[start:end]

    # =========================
    # OPTIONS (auto fill)
    # =========================
    models = sorted(set(l.get("meta", {}).get("model", "") for l in logs if l.get("meta")))
    devices = sorted(set(l.get("meta", {}).get("device", "") for l in logs if l.get("meta")))
    browsers = sorted(set(l.get("meta", {}).get("browser", "") for l in logs if l.get("meta")))
    channels = sorted(set(l.get("channel", "") for l in logs))

    # =========================
    # HTML ROWS
    # =========================
    rows = ""

    for i, l in enumerate(logs_page):
        meta = l.get("meta", {})

        rows += f"""
        <tr>
            <td>{l.get('id', i)}</td>
            <td>{l.get('time','')}</td>

            <td><span class="pill">{l.get('channel','web')}</span></td>

            <td>{l.get('message','')[:50]}</td>
            <td>{l.get('reply','')[:80]}</td>

            <td class="time">{l.get('response_time','-')}s</td>

            <td>{l.get('sources','-')}</td>

            <td>{l.get('ip','-')}</td>

            <td>
                <details>
                    <summary>View</summary>

                    <div class="box">
                        <b>SESSION ID</b><br>
                        {l.get('session_id','-')}<br><br>

                        <b>AI REPLY</b><br>
                        {l.get('reply','')}<br><br>

                        <div class="grid">
                            <div>
                                <b>RESPONSE TIME</b><br>
                                {l.get('response_time','-')}s
                            </div>
                            <div>
                                <b>MODEL</b><br>
                                {meta.get('model','deepseek')}
                            </div>
                            <div>
                                <b>DEVICE</b><br>
                                {meta.get('device','-')}
                            </div>
                            <div>
                                <b>BROWSER</b><br>
                                {meta.get('browser','-')}
                            </div>
                        </div>

                        <br>
                        <b>USER AGENT</b><br>
                        {meta.get('user_agent','-')}
                    </div>

                </details>
            </td>
        </tr>
        """

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
            display:grid;
            grid-template-columns: repeat(6, 1fr);
            gap:10px;
            background:#fff;
            padding:15px;
            border-radius:16px;
            box-shadow:0 6px 20px rgba(0,0,0,0.06);
            margin-bottom:15px;
        }}

        input, select {{
            padding:10px;
            border-radius:999px;
            border:1px solid #ddd;
        }}

        .btn {{
            background:linear-gradient(135deg,#3b82f6,#8b5cf6);
            color:white;
            border:none;
            border-radius:999px;
        }}

        /* TABLE */
        table {{
            width:100%;
            background:white;
            border-radius:16px;
            overflow:hidden;
            border-collapse:collapse;
        }}

        th {{
            background:#f3f4f6;
            text-align:left;
            padding:12px;
        }}

        td {{
            padding:12px;
            border-top:1px solid #eee;
            font-size:13px;
        }}

        .pill {{
            padding:4px 10px;
            border-radius:999px;
            background:#dcfce7;
        }}

        .time {{
            color:#16a34a;
            font-weight:bold;
        }}

        details {{
            cursor:pointer;
        }}

        .box {{
            background:#f9fafb;
            padding:12px;
            border-radius:12px;
            margin-top:10px;
        }}

        .grid {{
            display:grid;
            grid-template-columns: repeat(2, 1fr);
            gap:10px;
            margin-top:10px;
        }}
    </style>
    </head>

    <body>
    <div class="wrap">

    <h1>Enterprise Logs Dashboard</h1>

    <form class="filters">
        <input name="keyword" placeholder="搜尋關鍵字" value="{keyword}">
        <select name="channel">
            <option value="">Channel</option>
            {''.join([f'<option>{c}</option>' for c in channels])}
        </select>

        <select name="model">
            <option value="">Model</option>
            {''.join([f'<option>{m}</option>' for m in models])}
        </select>

        <select name="device">
            <option value="">Device</option>
            {''.join([f'<option>{d}</option>' for d in devices])}
        </select>

        <select name="browser">
            <option value="">Browser</option>
            {''.join([f'<option>{b}</option>' for b in browsers])}
        </select>

        <select name="size">
            <option value="10">10</option>
            <option value="20">20</option>
            <option value="50">50</option>
        </select>

        <button class="btn">搜尋</button>
    </form>

    <table>
        <tr>
            <th>ID</th>
            <th>Time</th>
            <th>Channel</th>
            <th>Question</th>
            <th>AI Reply</th>
            <th>Response Time</th>
            <th>Sources</th>
            <th>IP</th>
            <th>Detail</th>
        </tr>

        {rows}
    </table>

    </div>
    </body>
    </html>
    """)