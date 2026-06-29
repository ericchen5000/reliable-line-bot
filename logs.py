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

    with open(LOG_PATH, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except:
            return []


# =========================
# PLATFORM DETECT (fallback-safe)
# =========================
def get_platform(log):
    return log.get("platform", "LINE")


# =========================
# RESPONSE TIME
# =========================
def get_latency(log):
    return log.get("latency", "-")


# =========================
# UI
# =========================
@router.get("/logs", response_class=HTMLResponse)
def logs_ui(
    page: int = 1,
    size: int = 10,
    keyword: str = None,
    user: str = None,
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
    logs.sort(key=lambda x: x.get("time", ""), reverse=(sort == "desc"))

    # =========================
    # PAGINATION
    # =========================
    total = len(logs)
    start = (page - 1) * size
    end = start + size
    logs_page = logs[start:end]

    html = """
    <html>
    <head>
    <meta charset="utf-8"/>

    <style>
        body{
            margin:0;
            font-family: Arial;
            background:#f7f9fc;
            color:#1f2937;
        }

        .wrap{
            width:100%;
            padding:20px;
            box-sizing:border-box;
        }

        h1{
            font-size:20px;
            margin-bottom:15px;
        }

        /* FILTER */
        .filters{
            display:flex;
            flex-wrap:wrap;
            gap:10px;
            background:white;
            padding:15px;
            border-radius:14px;
            box-shadow:0 5px 15px rgba(0,0,0,0.05);
            margin-bottom:15px;
        }

        input, select{
            padding:10px 14px;
            border-radius:999px;
            border:1px solid #e5e7eb;
            background:#f9fafb;
        }

        /* BUTTON */
        .btn{
            padding:10px 16px;
            border-radius:999px;
            border:none;
            background:linear-gradient(135deg,#60a5fa,#a78bfa);
            color:white;
            cursor:pointer;
        }

        /* TABLE */
        table{
            width:100%;
            border-collapse:collapse;
            background:white;
            border-radius:14px;
            overflow:hidden;
            box-shadow:0 5px 15px rgba(0,0,0,0.05);
        }

        th{
            text-align:left;
            padding:12px;
            background:#f3f4f6;
            font-size:13px;
        }

        td{
            padding:12px;
            border-top:1px solid #eee;
            font-size:13px;
            vertical-align:top;
        }

        tr:hover{
            background:#f9fafb;
            cursor:pointer;
        }

        .badge{
            padding:4px 10px;
            border-radius:999px;
            background:linear-gradient(135deg,#93c5fd,#c4b5fd);
            display:inline-block;
        }

        .small{
            font-size:12px;
            color:#6b7280;
        }

        .expand{
            display:none;
            background:#fafafa;
        }

        .pill{
            padding:4px 10px;
            border-radius:999px;
            background:#e0f2fe;
            font-size:12px;
        }

        .latency{
            color:#16a34a;
            font-weight:bold;
        }

        .pagination{
            margin-top:15px;
        }

        .page{
            padding:6px 12px;
            border-radius:999px;
            background:white;
            margin-right:6px;
            text-decoration:none;
            border:1px solid #e5e7eb;
        }
    </style>

    <script>
        function toggle(id){
            var el = document.getElementById(id);
            el.style.display = (el.style.display === "table-row") ? "none" : "table-row";
        }
    </script>

    </head>

    <body>
    <div class="wrap">

    <h1>LOGS 系統</h1>

    <form class="filters" method="get">
        <input name="keyword" placeholder="關鍵字">
        <input name="user" placeholder="使用者ID">

        <select name="size">
            <option value="10">10筆</option>
            <option value="20">20筆</option>
            <option value="50">50筆</option>
        </select>

        <select name="sort">
            <option value="desc">最新</option>
            <option value="asc">最舊</option>
        </select>

        <button class="btn">搜尋</button>
    </form>

    <table>
        <tr>
            <th>時間</th>
            <th>使用者</th>
            <th>訊息</th>
            <th>回覆</th>
            <th>資訊</th>
        </tr>
    """

    for i, l in enumerate(logs_page):
        row_id = f"r_{i}"

        platform = get_platform(l)
        latency = get_latency(l)

        html += f"""
        <tr onclick="toggle('{row_id}')">
            <td>{l.get('time','')}</td>
            <td><span class="badge">{l.get('user','')}</span></td>
            <td>{l.get('message','')[:40]}</td>
            <td>{l.get('reply','')[:40]}</td>
            <td class="small">
                平台：<span class="pill">{platform}</span><br>
                回應時間：<span class="latency">{latency}s</span>
            </td>
        </tr>

        <tr id="{row_id}" class="expand">
            <td colspan="5">
                <b>完整訊息：</b><br>{l.get('message','')}<br><br>
                <b>完整回覆：</b><br>{l.get('reply','')}<br><br>
                <b>平台：</b>{platform}<br>
                <b>回應時間：</b>{latency}s
            </td>
        </tr>
        """

    html += """
    </table>

    <div class="pagination">
    """

    total_pages = max(1, (total // size) + 1)

    for p in range(1, total_pages + 1):
        html += f"<a class='page' href='?page={p}&size={size}'>{p}</a>"

    html += """
    </div>

    </div>
    </body>
    </html>
    """

    return HTMLResponse(html)