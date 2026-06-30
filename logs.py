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

        rows += f"""
        <tr>
            <td>{g(l,'id', i+1)}</td>
            <td>{g(l,'time')}</td>
            <td>{g(l,'platform','LINE')}</td>

            <td>{str(g(l,'message',''))[:45]}</td>
            <td>{str(g(l,'reply',''))[:70]}</td>

            <td>{g(l,'latency','-')}</td>
            <td>{g(l,'source','-')}</td>
            <td>{g(l,'ip','-')}</td>

            <td>
                <details>
                    <summary>DETAIL</summary>

                    <div style="padding:10px;background:#f9fafb;margin-top:8px;border-radius:10px">

                        <b>來源</b><br>{g(l,'source','-')}<br><br>

                        <b>IP</b><br>{g(l,'ip','-')}<br><br>

                        <b>DEVICE</b><br>{meta.get('device','-')}<br>
                        <b>BROWSER</b><br>{meta.get('browser','-')}<br><br>

                        <b>USER AGENT</b><br>{meta.get('user_agent','-')}<br><br>

                        <b>完整問題</b><br>{g(l,'message','')}<br><br>

                        <b>完整回覆</b><br>{g(l,'reply','')}
                    </div>
                </details>
            </td>
        </tr>
        """


    # =========================
    # OPTIONS
    # =========================
    page_opts = [10, 20, 50]

    def link(p):
        return f"?page={p}&size={size}&keyword={keyword}&platform={platform}&source={source}&sort_by={sort_by}&sort_order={sort_order}"


    # =========================
    # PAGE BAR
    # =========================
    pages = ""

    if page > 1:
        pages += f'<a href="{link(page-1)}">上一頁</a> '

    pages += f" 第 {page}/{total_pages} 頁 ｜ 總數 {total} ｜ 每頁 {size} "

    if page < total_pages:
        pages += f' <a href="{link(page+1)}">下一頁</a>'


    # =========================
    # SIZE OPTIONS
    # =========================
    size_select = "".join([f'<option value="{s}" {"selected" if s==size else ""}>{s}筆</option>' for s in page_opts])


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
    background:#f4f6fb;
    padding:16px;
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
    text-align:left;
    cursor:pointer;
}}

td {{
    padding:10px;
    border-top:1px solid #eee;
    font-size:13px;
}}

input, select {{
    padding:6px 10px;
    border-radius:999px;
    border:1px solid #ddd;
}}

.bar {{
    background:white;
    padding:12px;
    margin-bottom:10px;
    border-radius:12px;
    display:flex;
    gap:10px;
    flex-wrap:wrap;
}}

a {{
    margin:0 5px;
}}
</style>
</head>

<body>

<h2>LOGS</h2>

<form class="bar">

<input name="keyword" placeholder="關鍵字" value="{keyword}">
<input name="platform" placeholder="平台" value="{platform}">
<input name="source" placeholder="來源 FAQ/KB/AI" value="{source}">

<select name="size">
    {size_select}
</select>

<select name="sort_by">
    <option value="time">時間</option>
    <option value="platform">平台</option>
    <option value="latency">回應時間</option>
    <option value="source">來源</option>
</select>

<select name="sort_order">
    <option value="desc">DESC</option>
    <option value="asc">ASC</option>
</select>

<button>搜尋</button>
</form>

<div style="margin-bottom:10px">
{pages}
</div>

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
<th>DETAIL</th>
</tr>

{rows}
</table>

<div style="margin-top:10px">
{pages}
</div>

</body>
</html>
""")