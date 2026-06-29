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
# LIGHT DASHBOARD UI
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

    html = """
    <html>
    <head>
    <meta charset="utf-8"/>
    <title>LOGS</title>

    <style>
        body{
            margin:0;
            font-family: Arial;
            background:#f7f9fc;
            color:#1f2937;
        }

        .wrap{
            width:100%;
            padding:20px 30px;
            box-sizing:border-box;
        }

        h1{
            font-size:22px;
            margin-bottom:15px;
            font-weight:600;
        }

        /* =========================
           FILTER BAR
        ========================= */
        .filters{
            display:flex;
            flex-wrap:wrap;
            gap:10px;
            background:#ffffff;
            padding:15px;
            border-radius:16px;
            box-shadow:0 6px 18px rgba(0,0,0,0.05);
            margin-bottom:20px;
        }

        input, select{
            padding:10px 14px;
            border-radius:999px;
            border:1px solid #e5e7eb;
            outline:none;
            background:#f9fafb;
        }

        input:focus{
            border-color:#93c5fd;
            background:#fff;
        }

        /* =========================
           PILL BUTTON
        ========================= */
        .btn{
            padding:10px 16px;
            border-radius:999px;
            border:none;
            cursor:pointer;
            background:linear-gradient(135deg,#60a5fa,#a78bfa);
            color:white;
            font-weight:500;
            transition:0.2s;
        }

        .btn:hover{
            transform:scale(1.03);
            opacity:0.95;
        }

        /* =========================
           TABLE
        ========================= */
        table{
            width:100%;
            border-collapse:collapse;
            background:white;
            border-radius:16px;
            overflow:hidden;
            box-shadow:0 6px 18px rgba(0,0,0,0.05);
        }

        th{
            text-align:left;
            background:#f3f4f6;
            padding:14px;
            font-size:13px;
            color:#374151;
        }

        td{
            padding:12px 14px;
            border-top:1px solid #f1f1f1;
            font-size:13px;
            vertical-align:top;
        }

        tr:hover{
            background:#f9fafb;
            cursor:pointer;
        }

        /* =========================
           BADGE
        ========================= */
        .badge{
            display:inline-block;
            padding:4px 10px;
            border-radius:999px;
            background:linear-gradient(135deg,#93c5fd,#c4b5fd);
            color:#1e293b;
            font-size:12px;
        }

        /* =========================
           EXPAND ROW
        ========================= */
        .expand{
            display:none;
            background:#f9fafb;
        }

        /* =========================
           PAGINATION
        ========================= */
        .pagination{
            margin-top:20px;
        }

        .page{
            display:inline-block;
            padding:6px 12px;
            margin-right:6px;
            border-radius:999px;
            background:#fff;
            border:1px solid #e5e7eb;
            text-decoration:none;
            color:#374151;
        }

        .page:hover{
            background:#eef2ff;
        }

        .small{
            font-size:12px;
            color:#6b7280;
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

        <input name="model" placeholder="模型名稱">

        <select name="size">
            <option value="10">每頁10筆</option>
            <option value="20">每頁20筆</option>
            <option value="50">每頁50筆</option>
        </select>

        <select name="sort">
            <option value="desc">最新優先</option>
            <option value="asc">最舊優先</option>
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
        meta = l.get("meta", {})

        html += f"""
        <tr onclick="toggle('{row_id}')">
            <td>{l.get('time','')}</td>
            <td><span class="badge">{l.get('user','')}</span></td>
            <td>{l.get('message','')[:40]}</td>
            <td>{l.get('reply','')[:40]}</td>
            <td class="small">
                模型：{meta.get('model','-')}<br>
                裝置：{meta.get('device','-')}<br>
                瀏覽器：{meta.get('browser','-')}
            </td>
        </tr>

        <tr id="{row_id}" class="expand">
            <td colspan="5">
                <b>完整訊息：</b><br>{l.get('message','')}<br><br>
                <b>完整回覆：</b><br>{l.get('reply','')}<br><br>
                <b>Meta資訊：</b><pre>{json.dumps(meta, ensure_ascii=False, indent=2)}</pre>
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