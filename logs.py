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

    with open(LOG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


# =========================
# LOG DASHBOARD UI
# =========================
@router.get("/logs", response_class=HTMLResponse)
def logs_ui(
    page: int = 1,
    size: int = 10,
    keyword: str = None,
    user: str = None,
    model: str = None,
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

    if model:
        logs = [l for l in logs if l.get("meta", {}).get("model") == model]

    # =========================
    # SORT
    # =========================
    logs.sort(key=lambda x: x.get("time", ""), reverse=(sort == "desc"))

    # =========================
    # PAGINATION
    # =========================
    total = len(logs)
    start = (page - 1) * size
    end = start + size
    logs_page = logs[start:end]

    # =========================
    # HTML UI
    # =========================
    html = """
    <html>
    <head>
        <title>AI Logs Dashboard</title>
        <style>
            body {
                font-family: Arial;
                background: #0f172a;
                color: #e2e8f0;
                margin: 0;
                padding: 20px;
            }

            .container {
                max-width: 1200px;
                margin: auto;
            }

            h1 {
                color: #38bdf8;
            }

            .filters {
                background: #1e293b;
                padding: 15px;
                border-radius: 10px;
                margin-bottom: 20px;
            }

            input, select {
                padding: 8px;
                margin-right: 8px;
                border-radius: 6px;
                border: none;
            }

            table {
                width: 100%;
                border-collapse: collapse;
                background: #1e293b;
                border-radius: 10px;
                overflow: hidden;
            }

            th {
                background: #334155;
                padding: 12px;
                text-align: left;
                font-size: 14px;
            }

            td {
                padding: 10px;
                border-top: 1px solid #334155;
                font-size: 13px;
            }

            tr:hover {
                background: #334155;
                cursor: pointer;
            }

            .badge {
                padding: 2px 6px;
                border-radius: 6px;
                background: #0ea5e9;
                font-size: 12px;
            }

            .small {
                font-size: 12px;
                opacity: 0.8;
            }

            .expand {
                display: none;
                background: #0b1220;
            }

            .pagination a {
                color: #38bdf8;
                margin-right: 8px;
                text-decoration: none;
            }
        </style>

        <script>
            function toggle(id){
                var el = document.getElementById(id);
                el.style.display = (el.style.display === "none") ? "table-row" : "none";
            }
        </script>
    </head>
    <body>
    <div class="container">

    <h1>LOGS DASHBOARD</h1>

    <form class="filters" method="get">
        Keyword:
        <input name="keyword" placeholder="search...">

        User:
        <input name="user" placeholder="user id">

        Model:
        <input name="model" placeholder="gpt / deepseek">

        Size:
        <select name="size">
            <option value="10">10</option>
            <option value="20">20</option>
            <option value="50">50</option>
        </select>

        Sort:
        <select name="sort">
            <option value="desc">Newest</option>
            <option value="asc">Oldest</option>
        </select>

        <button>Apply</button>
    </form>

    <table>
        <tr>
            <th>Time</th>
            <th>User</th>
            <th>Message</th>
            <th>Reply</th>
            <th>Meta</th>
        </tr>
    """

    for i, l in enumerate(logs_page):
        row_id = f"row_{i}"

        meta = l.get("meta", {})

        html += f"""
        <tr onclick="toggle('{row_id}')">
            <td>{l.get('time','')}</td>
            <td><span class="badge">{l.get('user','')}</span></td>
            <td>{l.get('message','')[:40]}</td>
            <td>{l.get('reply','')[:40]}</td>
            <td class="small">
                model: {meta.get('model','-')}<br>
                device: {meta.get('device','-')}<br>
                browser: {meta.get('browser','-')}
            </td>
        </tr>

        <tr id="{row_id}" class="expand">
            <td colspan="5">
                <b>Full Message:</b><br>{l.get('message','')}<br><br>
                <b>Full Reply:</b><br>{l.get('reply','')}<br><br>
                <b>Meta:</b><br>{json.dumps(meta, ensure_ascii=False, indent=2)}
            </td>
        </tr>
        """

    html += """
    </table>

    <div class="pagination" style="margin-top:20px;">
    """

    total_pages = (total // size) + 1

    for p in range(1, total_pages + 1):
        html += f"<a href='?page={p}&size={size}'>{p}</a>"

    html += """
    </div>

    </div>
    </body>
    </html>
    """

    return HTMLResponse(html)