from fastapi import APIRouter
from fastapi.responses import HTMLResponse
import html
import json
import os
from collections import Counter
from datetime import datetime

router = APIRouter()

LOG_PATH = "logs/chat_logs.json"
FAQ_PATH = "data/faq.json"
INDEX_STATUS_PATH = "data/site_index_status.json"


def e(value):
    return html.escape(str(value))


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


@router.get("/", response_class=HTMLResponse)
def dashboard():
    logs = load_json(LOG_PATH, [])
    faq = load_json(FAQ_PATH, [])
    index_status = load_json(INDEX_STATUS_PATH, {})
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
            <td>{e(source)}</td>
            <td>{e(count)}</td>
        </tr>
        """

    if not source_rows:
        source_rows = "<tr><td colspan='2'>尚無資料</td></tr>"

    return HTMLResponse(f"""
    <html>
    <head>
    <meta charset="utf-8"/>
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
        }}
        .page {{ max-width:1180px; margin:0 auto; }}
        .topbar {{
            display:flex;
            justify-content:space-between;
            align-items:flex-end;
            gap:16px;
            margin-bottom:18px;
        }}
        h2 {{ margin:0; font-size:28px; }}
        .subtitle {{ margin:8px 0 0; color:var(--muted); font-size:13px; }}
        .nav {{ display:flex; gap:8px; flex-wrap:wrap; }}
        .nav a {{
            min-height:40px;
            padding:8px 14px;
            border-radius:8px;
            color:white;
            background:var(--button-bg);
            text-decoration:none;
            font-weight:700;
            display:inline-flex;
            align-items:center;
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
        table {{ width:100%; border-collapse:collapse; }}
        th, td {{ padding:12px; border-top:1px solid var(--border); text-align:left; vertical-align:top; }}
        th {{ color:var(--muted); background:var(--panel-soft); }}
        @media (max-width: 860px) {{
            body {{ padding:14px; }}
            .topbar {{ flex-direction:column; align-items:stretch; }}
            .grid, .wide {{ grid-template-columns:1fr; }}
            h2 {{ font-size:24px; }}
            .nav a {{ width:100%; justify-content:center; }}
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
            <nav class="nav">
                <a href="/logs">LOGS</a>
                <a href="/faq">FAQ</a>
                <a href="/site-index">網站索引</a>
            </nav>
        </header>

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
                <p>索引段落數：{e(index_status.get("total_chunks", 0))}</p>
                <p class="subtitle">索引排程預設每 24 小時重建一次，可在網站索引頁手動重建。</p>
            </div>
        </section>
    </main>
    </body>
    </html>
    """)
