from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
import html
import json
import os
from collections import Counter
from datetime import datetime

from services.search_index import INDEX_FILE, build_all_indexes, load_status
from analytics import (
    brand_counter,
    chart_html,
    chart_tabs,
    days_label,
    is_unanswered,
    repeated_questions,
    time_tabs,
    weekly_report_text,
)

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
        ("/test-chat", "測試"),
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


def health_checks():
    return [
        ("LINE_CHANNEL_ACCESS_TOKEN", bool(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))),
        ("LINE_CHANNEL_SECRET", bool(os.getenv("LINE_CHANNEL_SECRET"))),
        ("DEEPSEEK_API_KEY", bool(os.getenv("DEEPSEEK_API_KEY"))),
        ("FAQ 檔案", os.path.exists(FAQ_PATH)),
        ("URLS 檔案", os.path.exists("data/urls.json")),
        ("LOGS 目錄", os.path.exists("logs")),
        ("網站索引檔案", os.path.exists(INDEX_FILE)),
    ]


@router.get("/", response_class=HTMLResponse)
def dashboard(generate: int = 0, days: int = 7, chart: str = "bar"):
    if days not in {0, 7, 14, 30, 90}:
        days = 7

    if chart not in {"bar", "pie"}:
        chart = "bar"

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
    lead_logs = [
        item for item in logs
        if bool(item.get("need_followup")) or int(item.get("lead_score") or 0) >= 35
    ]
    pending_followups = [
        item for item in logs
        if bool(item.get("need_followup")) and item.get("followup_status", "pending") == "pending"
    ]
    report_logs = logs if days == 0 else [
        item for item in logs
        if parse_log_time(item.get("time", "")) and (datetime.now() - parse_log_time(item.get("time", ""))).days < days
    ]
    unanswered = [item for item in report_logs if is_unanswered(item)]
    brands = brand_counter(report_logs)
    repeats = repeated_questions(report_logs)
    report_sources = Counter(str(item.get("source", "-")) for item in report_logs)
    report_text = weekly_report_text(
        len(report_logs),
        len(unanswered),
        len(faq),
        index_status.get("total_chunks", index_count()),
        report_sources,
        brands,
        repeats,
        days,
    )
    report_html = f"""
        <section class="report-box" id="generated-report">
            <div class="report-head">
                <div>
                    <h3>AI 客服改善建議</h3>
                    <p class="subtitle">系統依近 {e(days_label(days))} LOGS 自動整理</p>
                </div>
                <button type="button" onclick="navigator.clipboard.writeText(document.getElementById('report-text').innerText)">複製建議</button>
            </div>
            <div class="report-text" id="report-text">{e(report_text)}</div>
        </section>
    """ if generate else ""

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

    health_rows = "".join(
        f"""
        <tr>
            <td data-label="項目">{e(name)}</td>
            <td data-label="狀態"><span class="status-pill {'ok' if ok else 'bad'}">{'OK' if ok else '缺少'}</span></td>
        </tr>
        """
        for name, ok in health_checks()
    )

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

    report_source_rows = "".join(
        f"<tr><td data-label='來源'>{e(source)}</td><td data-label='次數'>{count}</td></tr>"
        for source, count in report_sources.most_common(8)
    ) or "<tr><td colspan='2'>尚無資料</td></tr>"
    brand_rows = "".join(
        f"<tr><td data-label='品牌'>{e(brand)}</td><td data-label='提及次數'>{count}</td></tr>"
        for brand, count in brands.most_common(8)
    ) or "<tr><td colspan='2'>尚無品牌資料</td></tr>"
    repeat_rows = "".join(
        f"<tr><td data-label='問題'>{e(question)}</td><td data-label='次數'>{count}</td></tr>"
        for question, count in repeats[:8]
    ) or "<tr><td colspan='2'>尚無重複問題</td></tr>"
    source_chart = chart_html(report_sources.most_common(8), chart)
    brand_chart = chart_html(brands.most_common(8), chart, "尚無品牌資料")

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
        .value span {{ margin-left:4px; color:var(--muted); font-size:13px; font-weight:800; }}
        .wide {{
            display:grid;
            grid-template-columns:1fr 1fr;
            gap:14px;
        }}
        .section-head {{
            display:flex;
            align-items:flex-end;
            justify-content:space-between;
            gap:14px;
            margin:22px 0 14px;
        }}
        .toolbar {{
            display:flex;
            justify-content:space-between;
            gap:14px;
            flex-wrap:wrap;
            background:var(--panel);
            border:1px solid var(--border);
            border-radius:8px;
            box-shadow:var(--shadow);
            padding:14px;
            margin-bottom:14px;
        }}
        .tabs {{ display:flex; gap:8px; flex-wrap:wrap; margin-top:8px; }}
        .tab {{
            min-height:34px;
            padding:7px 11px;
            border-radius:999px;
            border:1px solid var(--border);
            color:var(--text);
            background:var(--panel);
            text-decoration:none;
            font-size:13px;
            font-weight:700;
            display:inline-flex;
            align-items:center;
            justify-content:center;
        }}
        .tab.active {{ color:white; background:var(--button-bg); border-color:transparent; }}
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
        .primary-action {{
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
        .status-pill {{
            display:inline-flex;
            min-height:28px;
            padding:5px 9px;
            border-radius:999px;
            font-size:12px;
            font-weight:800;
        }}
        .status-pill.ok {{ background:#dcfce7; color:#15803d; }}
        .status-pill.bad {{ background:#fee2e2; color:#b91c1c; }}
        .bar-chart {{ display:grid; gap:12px; }}
        .bar-row {{ display:grid; grid-template-columns:120px 1fr 42px; gap:10px; align-items:center; }}
        .bar-name {{ color:var(--text); font-size:13px; font-weight:700; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
        .bar-track {{ height:12px; border-radius:999px; background:var(--panel-soft); overflow:hidden; border:1px solid var(--border); }}
        .bar-fill {{ height:100%; border-radius:999px; background:var(--button-bg); min-width:8px; }}
        .bar-count {{ color:var(--accent); font-weight:800; font-size:13px; text-align:right; }}
        .empty-chart {{ color:var(--muted); padding:12px; border:1px dashed var(--border); border-radius:8px; background:var(--panel-soft); }}
        .pie-wrap {{ display:grid; grid-template-columns:180px 1fr; gap:18px; align-items:center; }}
        .pie {{ width:180px; aspect-ratio:1; border-radius:50%; box-shadow:inset 0 0 0 1px var(--border), 0 12px 28px rgba(15,23,42,0.08); }}
        .pie-legend {{ display:grid; gap:8px; }}
        .pie-legend-row {{ display:grid; grid-template-columns:14px minmax(0, 1fr) 42px; gap:8px; align-items:center; color:var(--text); font-size:13px; }}
        .pie-dot {{ width:10px; height:10px; border-radius:50%; }}
        .pie-name {{ overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }}
        .report-box {{ background:var(--panel); border:1px solid var(--border); border-radius:8px; box-shadow:var(--shadow); padding:16px; margin-bottom:14px; }}
        .report-head {{ display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:12px; }}
        .report-head h3 {{ margin:0; }}
        .report-text {{ padding:14px; border-radius:8px; background:var(--panel-soft); border:1px solid var(--border); white-space:pre-wrap; line-height:1.8; }}
        table {{ width:100%; border-collapse:collapse; }}
        th, td {{ padding:12px; border-top:1px solid var(--border); text-align:left; vertical-align:top; overflow-wrap:anywhere; word-break:break-word; }}
        th {{ color:var(--muted); background:var(--panel-soft); }}
        @media (max-width: 860px) {{
            body {{ padding:14px; }}
            .topbar {{ flex-direction:column; align-items:stretch; }}
            .section-head, .report-head {{ flex-direction:column; align-items:stretch; }}
            .primary-action {{ width:100%; }}
            .toolbar {{ display:grid; grid-template-columns:1fr; }}
            .tabs {{ display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); }}
            .tab {{ width:100%; }}
            .index-head {{ flex-direction:column; }}
            button {{ width:100%; }}
            .grid, .wide {{ grid-template-columns:1fr; }}
            h2 {{ font-size:24px; }}
            .pie-wrap {{ grid-template-columns:1fr; justify-items:center; }}
            .pie {{ width:min(220px, 72vw); }}
            .pie-legend {{ width:100%; }}
            .pie-name {{ white-space:normal; }}
            .bar-row {{ grid-template-columns:1fr 64px; }}
            .bar-name {{ grid-column:1 / -1; white-space:normal; }}
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
                <div class="label">可能商機</div>
                <div class="value">{e(len(lead_logs))}</div>
            </div>
            <div class="card">
                <div class="label">待人工追蹤</div>
                <div class="value">{e(len(pending_followups))}</div>
            </div>
            <div class="card">
                <div class="label">平均延遲</div>
                <div class="value">{e(avg_latency)}</div>
            </div>
        </section>

        <section class="card">
            <div class="index-head">
                <div>
                    <div class="label">網站索引與健康檢查</div>
                    <p class="subtitle">網站索引狀態、指定網站清單，以及服務必要設定集中在這裡。</p>
                </div>
                <div class="index-actions">
                    <form method="post" action="/dashboard/site-index/rebuild">
                        <button>立即建立索引</button>
                    </form>
                </div>
            </div>
            <section class="wide">
                <div>
                    <div class="label">網站索引狀態</div>
                    <p>最後更新：{e(index_status.get("last_run", "尚未建立"))}</p>
                    <p>索引段落數：{e(index_status.get("total_chunks", index_count()))}</p>
                    <p class="subtitle">索引排程預設每 24 小時重建一次，也可以手動立即建立。</p>
                </div>
                <div>
                    <div class="label">健康檢查</div>
                    <table>
                        <tr><th>項目</th><th>狀態</th></tr>
                        {health_rows}
                    </table>
                </div>
            </section>
            <table style="margin-top:14px;">
                <tr><th>網站</th><th>網址</th><th>抓取頁數</th><th>索引段落</th><th>失敗</th></tr>
                {site_rows}
            </table>
        </section>

        <section class="wide" style="margin-top:14px;">
            <div class="card">
                <div class="label">常見資料來源</div>
                <table>
                    <tr><th>來源</th><th>次數</th></tr>
                    {source_rows}
                </table>
            </div>
            <div class="card">
                <div class="label">商機 / 追蹤狀態</div>
                <p>可能商機：{e(len(lead_logs))} 筆</p>
                <p>待人工追蹤：{e(len(pending_followups))} 筆</p>
                <p class="subtitle">完整明細可到 LOGS 用「待追蹤」快速篩選查看。</p>
            </div>
        </section>

        <section class="section-head">
            <div>
                <h2>AI 客服週報</h2>
                <p class="subtitle">近 {e(days_label(days))} 客服營運摘要</p>
            </div>
            <a class="primary-action" href="/?days={days}&chart={e(chart)}&generate=1">一鍵產生建議</a>
        </section>
        <section class="toolbar">
            <div>
                <div class="label">統計期間</div>
                <div class="tabs">{time_tabs(days, chart).replace('/weekly-report', '/')}</div>
            </div>
            <div>
                <div class="label">圖表樣式</div>
                <div class="tabs">{chart_tabs(days, chart).replace('/weekly-report', '/')}</div>
            </div>
        </section>
        {report_html}
        <section class="grid">
            <div class="card"><div class="label">{e(days_label(days))}對話</div><div class="value">{len(report_logs)}<span>筆</span></div></div>
            <div class="card"><div class="label">未回答 / 待修</div><div class="value">{len(unanswered)}<span>筆</span></div></div>
            <div class="card"><div class="label">FAQ 總數</div><div class="value">{len(faq)}<span>筆</span></div></div>
            <div class="card"><div class="label">索引段落</div><div class="value">{e(index_status.get("total_chunks", index_count()))}<span>段</span></div></div>
        </section>
        <section class="wide">
            <div class="card"><h3>資料來源圖表</h3><div class="bar-chart">{source_chart}</div></div>
            <div class="card"><h3>品牌/產品圖表</h3><div class="bar-chart">{brand_chart}</div></div>
        </section>
        <section class="wide">
            <div class="card"><h3>資料來源分布</h3><table><tr><th>來源</th><th>次數</th></tr>{report_source_rows}</table></div>
            <div class="card"><h3>品牌/產品熱度</h3><table><tr><th>品牌</th><th>提及次數</th></tr>{brand_rows}</table></div>
        </section>
        <div class="card"><h3>重複問題</h3><table><tr><th>問題</th><th>次數</th></tr>{repeat_rows}</table></div>
        <script>
        if (window.location.search.includes("generate=1")) {{
            setTimeout(() => document.getElementById("generated-report")?.scrollIntoView({{behavior:"smooth", block:"start"}}), 120);
        }}
        </script>
    </main>
    </body>
    </html>
    """)


@router.post("/dashboard/site-index/rebuild")
def rebuild_site_index_from_dashboard(background_tasks: BackgroundTasks):
    background_tasks.add_task(build_all_indexes)
    return RedirectResponse("/", status_code=302)
