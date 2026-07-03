from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
import html
import json
import os
from collections import Counter
from datetime import datetime

from services.search_index import INDEX_FILE, build_all_indexes, load_status

router = APIRouter()

LOG_PATH = "logs/chat_logs.json"
FAQ_PATH = "data/faq.json"
INDEX_STATUS_PATH = "data/site_index_status.json"


def e(value):
    return html.escape(str(value))


def nav_html(active=""):
    items = [
        ("/", "Dashboard"),
        ("/logs", "LOGS"),
        ("/faq", "FAQ"),
        ("/weekly-report", "週報"),
        ("/test-chat", "測試"),
        ("/health", "健康檢查"),
    ]
    links = "".join(
        f'<a class="nav-link {"active" if active == label else ""}" href="{href}">{label}</a>'
        for href, label in items
    )
    return f'<button type="button" class="nav-toggle" onclick="this.closest(\'nav\').classList.toggle(\'open\')">☰ 選單</button><div class="nav-menu">{links}</div>'


def load_json(path, default):
    if not os.path.exists(path):
        return default

    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return default


def parse_log_time(value):
    try:
        return datetime.strptime(str(value), "%Y/%m/%d %H:%M:%S")
    except:
        return None


def index_count():
    if not os.path.exists(INDEX_FILE):
        return 0

    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return len(data) if isinstance(data, list) else 0
    except:
        return 0


@router.get("/", response_class=HTMLResponse)
def dashboard():
    logs = load_json(LOG_PATH, [])
    faq = load_json(FAQ_PATH, [])
    index_status = load_status() or load_json(INDEX_STATUS_PATH, {})
    today = datetime.now().date()

    today_logs = [
        item for item in logs
        if parse_log_time(item.get("time", "")) and parse_log_time(item.get("time", "")).date() == today
    ]

    latencies = []
    for item in logs:
        try:
            latencies.append(float(item.get("latency", 0)))
        except:
            pass

    avg_latency = round(sum(latencies) / len(latencies), 3) if latencies else "-"
    sources = Counter(str(item.get("source", "-")) for item in logs)
    top_sources = sources.most_common(5)

    source_rows = ""
    for source, count in top_sources:
        source_rows += f"""
        <tr>
            <td data-label="來源">{e(source)}</td>
            <td data-label="次數">{e(count)}</td>
        </tr>
        """

    if not source_rows:
        source_rows = "<tr><td colspan='2'>尚無資料</td></tr>"

    site_rows = ""
    for site in index_status.get("sites", []):
        site_rows += f"""
        <tr>
            <td data-label="網站">{e(site.get("title", "-"))}</td>
            <td data-label="網址">{e(site.get("url", "-"))}</td>
            <td data-label="抓取頁數">{e(site.get("pages", "-"))}</td>
            <td data-label="索引段落">{e(site.get("chunks", 0))}</td>
            <td data-label="失敗">{e(site.get("failed", 0))}</td>
        </tr>
        """

    if not site_rows:
        site_rows = "<tr><td colspan='5'>尚未建立索引</td></tr>"

    return HTMLResponse(f"""
    <html>
    <head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1"/>
    <style>
        :root {{
            --bg:#f6f7fb;
            --panel:#ffffff;
            --panel-soft:#f1f5f9;
            --text:#172033;
            --muted:#64748b;
            --border:#e2e8f0;
            --accent:#4f46e5;
            --button-bg:linear-gradient(135deg,#60a5fa,#a78bfa);
            --shadow:0 16px 40px rgba(15,23,42,0.08);
        }}
        * {{ box-sizing:border-box; }}
        body {{
            margin:0;
            font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC";
            background:radial-gradient(circle at top left, rgba(96,165,250,0.14), transparent 30%), var(--bg);
            padding:24px;
            color:var(--text);
            font-size:16px;
        }}
        .page {{ max-width:1280px; margin:0 auto; }}
        .topbar {{
            display:flex;
            justify-content:space-between;
            align-items:flex-end;
            gap:16px;
            margin-bottom:18px;
        }}
        h2 {{ margin:0; font-size:28px; }}
        .subtitle {{ margin:8px 0 0; color:var(--muted); font-size:13px; }}
        .nav {{ margin:0 0 18px; }}
        .nav-menu {{ display:flex; gap:8px; flex-wrap:wrap; }}
        .nav-toggle {{ display:none; }}
        .nav-link {{
            min-height:36px;
            padding:8px 12px;
            border-radius:8px;
            color:var(--text);
            background:var(--panel);
            border:1px solid var(--border);
            text-decoration:none;
            font-size:13px;
            font-weight:700;
            display:inline-flex;
            align-items:center;
            justify-content:center;
        }}
        .nav-link.active {{
            color:white;
            background:var(--button-bg);
            border:none;
        }}
        .grid {{
            display:grid;
            grid-template-columns:repeat(4, minmax(0, 1fr));
            gap:14px;
            margin-bottom:14px;
        }}
        .card {{
            background:var(--panel);
            border:1px solid var(--border);
            border-radius:8px;
            box-shadow:var(--shadow);
            padding:16px;
        }}
        .label {{ color:var(--muted); font-size:13px; font-weight:700; }}
        .value {{ margin-top:8px; font-size:28px; font-weight:800; }}
        .wide {{
            display:grid;
            grid-template-columns:1fr 1fr;
            gap:14px;
        }}
        .index-head {{
            display:flex;
            align-items:flex-start;
            justify-content:space-between;
            gap:14px;
            margin-bottom:12px;
        }}
        .index-actions {{
            display:flex;
            gap:10px;
            flex-wrap:wrap;
            align-items:center;
        }}
        button {{
            min-height:40px;
            padding:8px 14px;
            border-radius:8px;
            border:none;
            background:var(--button-bg);
            color:white;
            font-size:13px;
            font-weight:700;
            cursor:pointer;
            text-decoration:none;
            display:inline-flex;
            align-items:center;
            justify-content:center;
        }}
        table {{ width:100%; border-collapse:collapse; }}
        th, td {{ padding:12px; border-top:1px solid var(--border); text-align:left; vertical-align:top; overflow-wrap:anywhere; word-break:break-word; }}
        th {{ color:var(--muted); background:var(--panel-soft); }}
        @media (max-width: 860px) {{
            body {{ padding:14px; }}
            .topbar {{ flex-direction:column; align-items:stretch; }}
            .index-head {{ flex-direction:column; }}
            button {{ width:100%; }}
            .grid, .wide {{ grid-template-columns:1fr; }}
            h2 {{ font-size:24px; }}
            .nav-toggle {{ width:100%; display:flex; min-height:40px; padding:8px 12px; border-radius:8px; border:1px solid var(--border); background:var(--panel); color:var(--text); font-weight:700; align-items:center; justify-content:space-between; }}
            .nav-menu {{ display:none; grid-template-columns:1fr; gap:8px; margin-top:8px; }}
            .nav.open .nav-menu {{ display:grid; }}
            .nav-link {{ width:100%; justify-content:center; }}
            table, tbody, tr, td {{ display:block; width:100%; }}
            table {{ background:transparent; }}
            tr {{ border:1px solid var(--border); border-radius:8px; overflow:hidden; margin-bottom:12px; background:var(--panel); }}
            tr:first-child {{ display:none; }}
            td {{ display:grid; grid-template-columns:86px minmax(0, 1fr); gap:10px; border-top:1px solid var(--border); }}
            td:first-child {{ border-top:none; }}
            td::before {{ content:attr(data-label); color:var(--muted); font-weight:700; }}
        }}
    </style>
    </head>
    <body>
    <main class="page">
        <header class="topbar">
            <div>
                <h2>AI 客服 Dashboard</h2>
                <p class="subtitle">LINE 客服、FAQ、網站索引與回應品質總覽</p>
            </div>
        </header>

        <nav class="nav">{nav_html("Dashboard")}</nav>

        <section class="grid">
            <div class="card">
                <div class="label">今日對話</div>
                <div class="value">{e(len(today_logs))}</div>
            </div>
            <div class="card">
                <div class="label">總對話</div>
                <div class="value">{e(len(logs))}</div>
            </div>
            <div class="card">
                <div class="label">FAQ 筆數</div>
                <div class="value">{e(len(faq))}</div>
            </div>
            <div class="card">
                <div class="label">平均延遲</div>
                <div class="value">{e(avg_latency)}</div>
            </div>
        </section>

        <section class="wide">
            <div class="card">
                <div class="label">常見資料來源</div>
                <table>
                    <tr><th>來源</th><th>次數</th></tr>
                    {source_rows}
                </table>
            </div>
            <div class="card">
                <div class="label">網站索引狀態</div>
                <p>最後更新：{e(index_status.get("last_run", "尚未建立"))}</p>
                <p>索引段落數：{e(index_status.get("total_chunks", index_count()))}</p>
                <p class="subtitle">索引排程預設每 24 小時重建一次，也可以在下方立即建立。</p>
            </div>
        </section>

        <section class="card" style="margin-top:14px;">
            <div class="index-head">
                <div>
                    <div class="label">網站索引管理</div>
                    <p class="subtitle">依照 data/urls.json 的網站清單建立本地搜尋索引。</p>
                </div>
                <div class="index-actions">
                    <form method="post" action="/dashboard/site-index/rebuild">
                        <button>立即建立索引</button>
                    </form>
                </div>
            </div>
            <table>
                <tr><th>網站</th><th>網址</th><th>抓取頁數</th><th>索引段落</th><th>失敗</th></tr>
                {site_rows}
            </table>
        </section>
    </main>
    </body>
    </html>
    """)


@router.post("/dashboard/site-index/rebuild")
def rebuild_site_index_from_dashboard(background_tasks: BackgroundTasks):
    background_tasks.add_task(build_all_indexes)
    return RedirectResponse("/", status_code=302)
