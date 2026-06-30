from fastapi import APIRouter
from fastapi.responses import HTMLResponse
import json
import os

router = APIRouter()

LOG_PATH = "logs/chat_logs.json"


# =========================
# LOAD
# =========================
def load_logs():
    if not os.path.exists(LOG_PATH):
        return []
    try:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []


def g(d, k, default="-"):
    return d.get(k, default) if isinstance(d, dict) else default


# =========================
# SORT MAP
# =========================
SORT_MAP = {
    "id": "id",
    "time": "time",
    "platform": "platform",
    "latency": "latency",
    "ip": "ip",
    "source": "source",
}


# =========================
# UI
# =========================
@router.get("/logs", response_class=HTMLResponse)
def logs_ui(
    page: int = 1,
    size: int = 10,
    keyword: str = "",
    platform: str = "",
    source: str = "",
    sort_by: str = "time",
    sort_order: str = "desc"
):

    logs = load_logs()

    # =========================
    # FILTER
    # =========================
    if keyword:
        k = keyword.lower()
        logs = [
            l for l in logs
            if k in str(l.get("message", "")).lower()
            or k in str(l.get("reply", "")).lower()
            or k in str(l.get("source", "")).lower()
        ]

    if platform:
        logs = [l for l in logs if l.get("platform") == platform]

    if source:
        logs = [l for l in logs if l.get("source") == source]

    # =========================
    # SORT
    # =========================
    sort_key = SORT_MAP.get(sort_by, "time")
    reverse = (sort_order == "desc")

    logs.sort(key=lambda x: x.get(sort_key, ""), reverse=reverse)

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

        # =========================
        # MAIN ROW
        # =========================
        rows += f"""
        <tr>
            <td>{g(l,'id', i+1)}</td>
            <td>{g(l,'time')}</td>
            <td><span class="pill">{g(l,'platform','LINE')}</span></td>

            <td class="msg">{str(g(l,'message',''))[:45]}</td>
            <td class="reply-cell">{str(g(l,'reply',''))[:60]}</td>

            <td class="latency">{g(l,'latency','-')}</td>
            <td class="source">{g(l,'source','-')}</td>
            <td class="ip">{g(l,'ip','-')}</td>

            <td>
                <button class="btn" onclick="toggleDetail({i})">點擊查看</button>
            </td>
        </tr>

        <!-- =========================
             DETAIL ROW (FULL WIDTH)
        ========================= -->
        <tr id="detail-{i}" style="display:none;">
            <td colspan="9">
                <div class="detail-box">

                    <div class="grid">
                        <div><b>DEVICE</b><br>{meta.get('device','-')}</div>
                        <div><b>BROWSER</b><br>{meta.get('browser','-')}</div>
                        <div><b>USER AGENT</b><br>{meta.get('user_agent','-')}</div>
                        <div><b>來源</b><br>{g(l,'source','-')}</div>
                        <div><b>IP</b><br>{g(l,'ip','-')}</div>
                    </div>

                    <div class="block">
                        <b>問題</b>
                        <div>{g(l,'message','')}</div>
                    </div>

                    <div class="block">
                        <b>回覆</b>
                        <div>{g(l,'reply','')}</div>
                    </div>

                </div>
            </td>
        </tr>
        """

    # =========================
    # PAGE LINK
    # =========================
    def link(p):
        return f"?page={p}&size={size}&keyword={keyword}&platform={platform}&source={source}&sort_by={sort_by}&sort_order={sort_order}"

    pages = ""
    if page > 1:
        pages += f'<a href="{link(page-1)}">← 上一頁</a> '

    pages += f"<span class='info'>第 {page}/{total_pages} 頁 ｜ 總數 {total} ｜ 每頁 {size}</span> "

    if page < total_pages:
        pages += f'<a href="{link(page+1)}">下一頁 →</a>'

    # =========================
    # SIZE OPTIONS
    # =========================
    page_opts = [10, 20, 50]
    size_select = "".join(
        [f'<option value="{s}" {"selected" if s==size else ""}>{s} 筆</option>' for s in page_opts]
    )

    # =========================
    # HTML
    # =========================
    return HTMLResponse(f"""
<html>
<head>
<meta charset="utf-8"/>
</head>

<body>

<h2>LOGS DASHBOARD</h2>

<div class="pages">{pages}</div>

<table>
    <tr>
        <th>ID</th>
        <th>時間</th>
        <th>平台</th>
        <th>問題</th>
        <th>回覆</th>
        <th>延遲</th>
        <th>來源</th>
        <th>IP</th>
        <th>操作</th>
    </tr>

    {rows}
</table>

<div class="pages">{pages}</div>

<style>
body {{
    margin:0;
    font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC";
    background:#f4f6fb;
    padding:18px;
}}

table {{
    width:100%;
    border-collapse:collapse;
    background:white;
    border-radius:12px;
    overflow:hidden;
}}

th {{
    background:#eef2ff;
    padding:10px;
}}

td {{
    padding:10px;
    border-top:1px solid #eee;
    font-size:13px;
}}

.pill {{
    padding:4px 10px;
    border-radius:999px;
    background:#dbeafe;
}}

.reply-cell {{
    max-width:180px;
    overflow:hidden;
    text-overflow:ellipsis;
    white-space:nowrap;
}}

.btn {{
    padding:6px 10px;
    border:none;
    border-radius:999px;
    background:#3b82f6;
    color:white;
    cursor:pointer;
}}

.detail-box {{
    padding:14px;
    background:#f8fafc;
}}

.grid {{
    display:grid;
    grid-template-columns:repeat(3,1fr);
    gap:10px;
    font-size:12px;
}}

.block {{
    margin-top:10px;
}}

.pages {{
    margin:12px 0;
    text-align:center;
}}

.pages a {{
    margin:0 5px;
}}

.info {{
    color:#666;
    font-size:13px;
}}
</style>

<script>
function toggleDetail(i) {{
    const row = document.getElementById("detail-" + i);
    if (row.style.display === "none") {{
        row.style.display = "table-row";
    }} else {{
        row.style.display = "none";
    }}
}}
</script>

</body>
</html>
""")