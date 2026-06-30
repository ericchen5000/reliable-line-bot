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
# PLATFORM DETECT
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

    if keyword:
        logs = [
            l for l in logs
            if keyword.lower() in l.get("message", "").lower()
            or keyword.lower() in l.get("reply", "").lower()
        ]

    if user:
        logs = [l for l in logs if l.get("user") == user]

    logs.sort(key=lambda x: x.get("time", ""), reverse=(sort == "desc"))

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
            font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC",Arial;
            background:#f5f7fb;
            color:#111827;
        }

        .wrap{
            width:100%;
            padding:24px;
            box-sizing:border-box;
        }

        h1{
            font-size:26px;
            font-weight:700;
            margin-bottom:18px;
            letter-spacing:0.5px;
        }

        /* =========================
           FILTER BAR (soft glass)
        ========================= */
        .filters{
            display:flex;
            flex-wrap:wrap;
            gap:10px;
            background:rgba(255,255,255,0.8);
            backdrop-filter: blur(10px);
            padding:14px;
            border-radius:18px;
            box-shadow:0 8px 24px rgba(0,0,0,0.06);
            margin-bottom:18px;
        }

        input, select{
            padding:10px 14px;
            border-radius:999px;
            border:1px solid #e5e7eb;
            background:#ffffff;
            outline:none;
            transition:0.2s;
        }

        input:focus{
            border-color:#93c5fd;
            box-shadow:0 0 0 3px rgba(147,197,253,0.3);
        }

        /* =========================
           BUTTON (pill gradient)
        ========================= */
        .btn{
            padding:10px 18px;
            border-radius:999px;
            border:none;
            cursor:pointer;
            background:linear-gradient(135deg,#60a5fa,#a78bfa);
            color:white;
            font-weight:600;
            transition:0.2s;
        }

        .btn:hover{
            transform:translateY(-1px);
            opacity:0.95;
        }

        /* =========================
           TABLE (clean modern)
        ========================= */
        table{
            width:100%;
            border-collapse:separate;
            border-spacing:0;
            background:white;
            border-radius:16px;
            overflow:hidden;
            box-shadow:0 10px 28px rgba(0,0,0,0.06);
        }

        th{
            text-align:left;
            padding:14px;
            font-size:13px;
            background:#f3f4f6;
            color:#374151;
            position:sticky;
            top:0;
        }

        td{
            padding:14px;
            border-top:1px solid #f1f1f1;
            font-size:13px;
            vertical-align:top;
        }

        tr:hover{
            background:#f9fafb;
        }

        /* =========================
           BADGE (soft pill)
        ========================= */
        .badge{
            display:inline-block;
            padding:4px 10px;
            border-radius:999px;
            background:linear-gradient(135deg,#93c5fd,#c4b5fd);
            color:#1e293b;
            font-size:12px;
        }

        .small{
            font-size:12px;
            color:#6b7280;
        }

        /* =========================
           METRICS
        ========================= */
        .pill{
            display:inline-block;
            padding:4px 10px;
            border-radius:999px;
            background:#e0f2fe;
            font-size:12px;
            margin-top:2px;
        }

        .latency{
            color:#16a34a;
            font-weight:700;
        }

        /* =========================
           EXPAND
        ========================= */
        .expand{
            display:none;
            background:#fafafa;
        }

        /* =========================
           PAGINATION
        ========================= */
        .pagination{
            margin-top:18px;
        }

        .page{
            display:inline-block;
            padding:6px 12px;
            border-radius:999px;
            background:white;
            margin-right:6px;
            text-decoration:none;
            border:1px solid #e5e7eb;
            transition:0.2s;
        }

        .page:hover{
            background:#eef2ff;
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
        <input name="keyword" placeholder="關鍵字搜尋">
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
                <b>完整回覆：</b><br>{l.get('reply','')}
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