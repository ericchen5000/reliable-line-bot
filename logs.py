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
# LOGS UI (PRO)
# =========================
@router.get("/logs", response_class=HTMLResponse)
def logs_ui(
    user: str = None,
    keyword: str = None,
    sort: str = "desc",
    page: int = 1,
    size: int = 20
):

    logs = load_logs()

    # =========================
    # FILTER
    # =========================
    if user:
        logs = [l for l in logs if l.get("user") == user]

    if keyword:
        logs = [
            l for l in logs
            if keyword.lower() in l.get("message", "").lower()
            or keyword.lower() in l.get("reply", "").lower()
        ]

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
    # HTML
    # =========================
    html = """
    <html>
    <head>
        <title>LOGS Dashboard</title>
        <style>
            body { font-family: Arial; background:#f4f4f4; padding:20px; }
            table { width:100%; border-collapse: collapse; background:white; }
            th, td { border:1px solid #ddd; padding:8px; font-size:14px; }
            th { background:#333; color:white; }
            tr:hover { background:#f1f1f1; cursor:pointer; }
            .box { margin-bottom:15px; }
            input, select { padding:6px; margin-right:5px; }
            .expand { display:none; background:#fafafa; }
        </style>

        <script>
            function toggleRow(id){
                var el = document.getElementById(id);
                if(el.style.display === "none"){
                    el.style.display = "table-row";
                } else {
                    el.style.display = "none";
                }
            }
        </script>
    </head>
    <body>

    <h2>LOGS DASHBOARD</h2>

    <form method="get" class="box">
        User: <input name="user">
        Keyword: <input name="keyword">
        Sort:
        <select name="sort">
            <option value="desc">DESC</option>
            <option value="asc">ASC</option>
        </select>
        <button>Search</button>
    </form>

    <table>
        <tr>
            <th>Time</th>
            <th>User</th>
            <th>Message</th>
            <th>Reply</th>
        </tr>
    """

    for i, log in enumerate(logs_page):

        detail_id = f"detail_{i}"

        html += f"""
        <tr onclick="toggleRow('{detail_id}')">
            <td>{log.get('time','')}</td>
            <td>{log.get('user','')}</td>
            <td>{log.get('message','')[:50]}</td>
            <td>{log.get('reply','')[:50]}</td>
        </tr>

        <tr id="{detail_id}" class="expand" style="display:none;">
            <td colspan="4">
                <b>Full Message:</b><br>{log.get('message','')}<br><br>
                <b>Full Reply:</b><br>{log.get('reply','')}<br>
            </td>
        </tr>
        """

    html += """
    </table>
    """

    # =========================
    # PAGINATION UI
    # =========================
    total_pages = (total // size) + 1

    html += "<div style='margin-top:15px;'>"

    for p in range(1, total_pages + 1):
        html += f"<a href='?page={p}&size={size}' style='margin-right:8px;'>{p}</a>"

    html += "</div>"

    html += """
    </body>
    </html>
    """

    return HTMLResponse(html)