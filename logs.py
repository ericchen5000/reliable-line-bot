from fastapi import APIRouter, Query
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
# LOGS UI
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
            if keyword.lower() in l.get("message", "").lower()
            or keyword.lower() in l.get("reply", "").lower()
        ]

    if user:
        logs = [l for l in logs if l.get("user") == user]

    # =========================
    # SORT
    # =========================
    logs.sort(
        key=lambda x: x.get("time", ""),
        reverse=(sort == "desc")
    )

    # =========================
    # PAGINATION
    # =========================
    total = len(logs)
    start = (page - 1) * size
    end = start + size
    logs_page = logs[start:end]

    # =========================
    # HTML ROWS
    # =========================
    html_rows = ""

    for i, l in enumerate(logs_page):
        meta = l.get("meta", {})

        html_rows += f"""
        <tr>
            <td>{l.get('time','')}</td>
            <td>{l.get('user','')}</td>
            <td>{l.get('message','')[:50]}</td>
            <td>{l.get('reply','')[:80]}</td>
            <td>
                平台：{l.get('platform','LINE')}<br>
                回應時間：{l.get('latency','-')}s
            </td>
        </tr>
        """

    # =========================
    # HTML
    # =========================
    html = f"""
    <html>
    <head>
    <meta charset="utf-8"/>
    <title>LOGS</title>

    <style>
        body {{
            font-family: Arial;
            background:#f5f7fb;
            margin:0;
            padding:20px;
        }}

        h1 {{
            margin-bottom:20px;
        }}

        .box {{
            background:white;
            padding:15px;
            border-radius:12px;
            box-shadow:0 4px 12px rgba(0,0,0,0.05);
        }}

        input {{
            padding:8px;
            border-radius:20px;
            border:1px solid #ddd;
            margin-right:5px;
        }}

        table {{
            width:100%;
            border-collapse:collapse;
            margin-top:15px;
        }}

        th, td {{
            border-bottom:1px solid #eee;
            padding:10px;
            font-size:13px;
        }}

        th {{
            background:#f3f4f6;
            text-align:left;
        }}
    </style>

    </head>

    <body>

    <h1>LOGS 系統</h1>

    <div class="box">

        <form method="get">
            <input name="keyword" placeholder="關鍵字">
            <input name="user" placeholder="使用者">
            <button>搜尋</button>
        </form>

        <table>
            <tr>
                <th>時間</th>
                <th>使用者</th>
                <th>訊息</th>
                <th>回覆</th>
                <th>資訊</th>
            </tr>

            {html_rows}

        </table>

    </div>

    </body>
    </html>
    """

    return HTMLResponse(html)