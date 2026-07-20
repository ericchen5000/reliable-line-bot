from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import HTMLResponse, RedirectResponse
import html
import json
import os
from collections import Counter
from datetime import datetime

from services.search_index import INDEX_FILE, build_all_indexes, load_status
from admin_ui import admin_bar_css, admin_bar_html
import admin_tools
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
        ("/faq", "知識管理"),
        ("/test-chat", "測試"),
        ("/admin/users", "帳號管理"),
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


def status_level(ok, warn=False):
    if ok:
        return "ok"
    return "warn" if warn else "bad"


def status_card(title, value, detail, level="ok"):
    label = {"ok": "正常", "warn": "注意", "bad": "異常"}.get(level, "正常")
    return f"""
    <div class="status-card">
        <span class="status-light {level}"></span>
        <div>
            <b>{e(title)}</b>
            <strong>{e(value)}</strong>
            <small>{e(detail)}</small>
        </div>
        <em>{e(label)}</em>
    </div>
    """


def source_group(value):
    source = str(value or "-").strip()

    if "網站索引" in source or source.startswith("http") or source.startswith("URL-"):
        return "網站索引"

    if source in {"AI", "AI客服"}:
        return "AI 客服"

    if source.startswith("KB") or source.startswith("知識庫"):
        return "知識庫"

    return source or "-"


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, generate: int = 0, days: int = 7, chart: str = "bar", notice: str = ""):
    readonly = admin_tools.is_readonly_admin(request)
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
    grouped_sources = Counter(source_group(item.get("source", "-")) for item in report_logs)
    platforms = Counter(str(item.get("platform", "LINE") or "LINE") for item in report_logs)
    quality_counts = Counter()
    lead_intents = Counter()

    for item in report_logs:
        quality = str(item.get("quality", "") or "")
        quality_counts[{
            "good": "良好",
            "fix": "待修",
            "wrong": "錯誤",
        }.get(quality, "未標記")] += 1

        if bool(item.get("need_followup")) or int(item.get("lead_score") or 0) >= 35:
            lead_intents[str(item.get("intent", "一般詢問") or "一般詢問")] += 1

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

    health_rows = "".join(
        f"""
        <tr>
            <td data-label="項目">{e(name)}</td>
            <td data-label="狀態"><span class="status-pill {'ok' if ok else 'bad'}">{'OK' if ok else '缺少'}</span></td>
        </tr>
        """
        for name, ok in health_checks()
    )
    checks = health_checks()
    missing_checks = [name for name, ok in checks if not ok]
    index_chunks = int(index_status.get("total_chunks", index_count()) or 0)
    index_failed = sum(int(site.get("failed", 0) or 0) for site in index_status.get("sites", []))
    status_cards = "".join([
        status_card(
            "系統設定",
            f"{len(checks) - len(missing_checks)} / {len(checks)}",
            "必要環境與資料檔檢查",
            status_level(not missing_checks, warn=bool(missing_checks))
        ),
        status_card(
            "LINE 串接",
            "已設定" if all(ok for name, ok in checks if name.startswith("LINE_")) else "未完整",
            "Webhook 與 Access Token 狀態",
            status_level(all(ok for name, ok in checks if name.startswith("LINE_")))
        ),
        status_card(
            "網站索引",
            f"{index_chunks} 段",
            f"失敗 {index_failed} 筆，最後更新：{index_status.get('last_run', '尚未建立')}",
            "ok" if index_chunks and index_failed == 0 else ("warn" if index_chunks else "bad")
        ),
        status_card(
            "AI 串接",
            "已設定" if os.getenv("DEEPSEEK_API_KEY") else "未設定",
            "DeepSeek API Key 狀態",
            status_level(bool(os.getenv("DEEPSEEK_API_KEY")))
        ),
    ])

    site_rows = ""
    failure_rows = ""
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
        for failure in site.get("failures", [])[:8]:
            status_code = failure.get("status_code") or "-"
            text_length = failure.get("text_length")
            detail = f"狀態：{status_code}"
            if text_length is not None:
                detail += f"｜文字長度：{text_length}"
            failure_rows += f"""
            <tr>
                <td data-label="網站">{e(site.get("title", "-"))}</td>
                <td data-label="失敗網址"><a href="{e(failure.get("url", ""))}" target="_blank" rel="noopener">{e(failure.get("url", "-"))}</a></td>
                <td data-label="原因">{e(failure.get("reason", "-"))}</td>
                <td data-label="補充">{e(detail)}</td>
            </tr>
            """

    if not site_rows:
        site_rows = "<tr><td colspan='5'>尚未建立索引</td></tr>"

    failure_html = ""
    if failure_rows:
        failure_html = f"""
        <div class="failure-panel">
            <div class="failure-head">
                <div>
                    <div class="label">索引失敗清單</div>
                    <p class="subtitle">列出本次建立索引時抓不到內容的頁面，方便回頭檢查網站頁面。</p>
                </div>
            </div>
            <table>
                <tr><th>網站</th><th>失敗網址</th><th>原因</th><th>補充</th></tr>
                {failure_rows}
            </table>
        </div>
        """

    repeat_rows = "".join(
        f"<tr><td data-label='問題'>{e(question)}</td><td data-label='次數'>{count}</td></tr>"
        for question, count in repeats[:8]
    ) or "<tr><td colspan='2'>尚無重複問題</td></tr>"
    platform_chart = chart_html(platforms.most_common(8), chart, "尚無平台資料")
    source_chart = chart_html(grouped_sources.most_common(8), chart)
    quality_chart = chart_html(quality_counts.most_common(8), chart, "尚無品質資料")
    lead_chart = chart_html(lead_intents.most_common(8), chart, "尚無商機資料")
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
            min-height:100vh;
            padding:24px;
            color:var(--text);
            font-size:16px;
        }}
        body.dark {{
            --bg:#0f172a;
            --panel:#162033;
            --panel-soft:#1e293b;
            --text:#e5edf7;
            --muted:#94a3b8;
            --border:#334155;
            --accent:#93c5fd;
            --shadow:0 16px 40px rgba(0,0,0,0.28);
        }}
        .page {{ max-width:1400px; margin:0 auto; }}
        .topbar {{
            display:flex;
            justify-content:space-between;
            align-items:flex-end;
            gap:16px;
            margin-bottom:18px;
        }}
        .theme-control {{
            flex:0 0 auto;
            display:flex;
            align-items:center;
            gap:10px;
            padding:8px 10px 8px 14px;
            border-radius:999px;
            border:1px solid var(--border);
            background:var(--panel);
            box-shadow:var(--shadow);
            color:var(--muted);
            font-size:13px;
            font-weight:700;
            cursor:pointer;
            user-select:none;
        }}
        .switch {{ position:relative; width:52px; height:30px; flex:0 0 auto; }}
        .switch input {{ position:absolute; opacity:0; width:0; height:0; }}
        .slider {{
            position:absolute;
            inset:0;
            border-radius:999px;
            background:#cbd5e1;
            transition:background 0.2s ease;
            box-shadow:inset 0 1px 3px rgba(15,23,42,0.18);
        }}
        .slider::before {{
            content:"";
            position:absolute;
            width:26px;
            height:26px;
            left:2px;
            top:2px;
            border-radius:50%;
            background:#fff;
            box-shadow:0 2px 8px rgba(15,23,42,0.25);
            transition:transform 0.2s ease;
        }}
        .switch input:checked + .slider {{ background:linear-gradient(135deg,#60a5fa,#a78bfa); }}
        .switch input:checked + .slider::before {{ transform:translateX(22px); }}
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
            border:1px solid transparent;
        }}
        .grid {{
            display:grid;
            grid-template-columns:repeat(4, minmax(0, 1fr));
            gap:14px;
            margin-bottom:14px;
        }}
        .status-grid {{
            display:grid;
            grid-template-columns:repeat(4, minmax(0, 1fr));
            gap:14px;
            margin:0 0 18px;
        }}
        .status-card {{
            position:relative;
            display:grid;
            grid-template-columns:18px minmax(0, 1fr);
            gap:10px;
            padding:14px;
            border-radius:8px;
            border:1px solid var(--border);
            background:var(--panel);
            box-shadow:var(--shadow);
            min-height:112px;
        }}
        .status-card b {{
            display:block;
            color:var(--muted);
            font-size:12px;
            margin-bottom:8px;
        }}
        .status-card strong {{
            display:block;
            color:var(--text);
            font-size:21px;
            line-height:1.2;
        }}
        .status-card small {{
            display:block;
            margin-top:7px;
            color:var(--muted);
            font-size:12px;
            line-height:1.45;
        }}
        .status-card em {{
            position:absolute;
            top:12px;
            right:12px;
            color:var(--muted);
            font-size:11px;
            font-style:normal;
            font-weight:900;
        }}
        .status-light {{
            width:12px;
            height:12px;
            border-radius:50%;
            margin-top:4px;
            box-shadow:0 0 0 4px rgba(100,116,139,0.12);
            background:#94a3b8;
        }}
        .status-light.ok {{ background:#22c55e; box-shadow:0 0 0 4px rgba(34,197,94,0.14); }}
        .status-light.warn {{ background:#f59e0b; box-shadow:0 0 0 4px rgba(245,158,11,0.14); }}
        .status-light.bad {{ background:#ef4444; box-shadow:0 0 0 4px rgba(239,68,68,0.14); }}
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
        .ops-grid {{
            display:grid;
            grid-template-columns:minmax(0,1.25fr) minmax(0,0.75fr);
            gap:14px;
            margin-top:18px;
        }}
        .section-head {{
            display:flex;
            align-items:flex-end;
            justify-content:space-between;
            gap:14px;
            margin:22px 0 14px;
        }}
        .section-actions {{
            display:flex;
            gap:8px;
            flex-wrap:wrap;
            justify-content:flex-end;
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
            color:var(--muted);
            background:var(--panel-soft);
            text-decoration:none;
            font-size:13px;
            font-weight:700;
            display:inline-flex;
            align-items:center;
            justify-content:center;
        }}
        .tab.active {{ color:var(--accent); background:var(--panel-soft); border-color:rgba(96,165,250,0.45); box-shadow:inset 0 0 0 1px rgba(96,165,250,0.18); }}
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
        .muted-pill {{
            min-height:36px;
            padding:8px 12px;
            border-radius:8px;
            background:var(--panel-soft);
            border:1px solid var(--border);
            color:var(--muted);
            font-size:13px;
            font-weight:800;
            display:inline-flex;
            align-items:center;
            justify-content:center;
        }}
        .index-summary {{
            display:grid;
            grid-template-columns:repeat(2, minmax(0, 1fr));
            gap:12px;
            margin-bottom:14px;
        }}
        .mini-stat {{
            padding:12px;
            border-radius:8px;
            border:1px solid var(--border);
            background:var(--panel-soft);
        }}
        .mini-stat b {{
            display:block;
            margin-top:6px;
            color:var(--text);
            font-size:18px;
        }}
        .failure-panel {{
            margin-top:14px;
            padding-top:14px;
            border-top:1px solid var(--border);
        }}
        .failure-head {{
            display:flex;
            justify-content:space-between;
            gap:12px;
            margin-bottom:10px;
        }}
        .failure-panel a {{
            color:var(--accent);
            overflow-wrap:anywhere;
            text-decoration:none;
            font-weight:700;
        }}
        .failure-panel a:hover {{ text-decoration:underline; }}
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
        .notice-card {{ color:#3730a3; background:#e0e7ff; border-color:#c7d2fe; font-weight:800; }}
        .toast {{
            position:fixed;
            right:22px;
            top:82px;
            z-index:1200;
            max-width:360px;
            padding:12px 14px;
            border-radius:8px;
            border:1px solid rgba(96,165,250,0.35);
            background:var(--panel);
            color:var(--text);
            box-shadow:var(--shadow);
            font-size:13px;
            font-weight:800;
            transition:opacity 0.2s ease, transform 0.2s ease;
        }}
        .report-head {{ display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:12px; }}
        .report-head h3 {{ margin:0; }}
        .report-text {{ padding:14px; border-radius:8px; background:var(--panel-soft); border:1px solid var(--border); white-space:pre-wrap; line-height:1.8; }}
        table {{ width:100%; border-collapse:collapse; }}
        th, td {{ padding:12px; border-top:1px solid var(--border); text-align:left; vertical-align:top; overflow-wrap:anywhere; word-break:break-word; }}
        th {{ color:var(--muted); background:var(--panel-soft); }}
        {admin_bar_css()}
        @media (max-width: 860px) {{
            body {{ padding:14px; }}
            .topbar {{ flex-direction:column; align-items:stretch; }}
            .theme-control {{ width:100%; justify-content:space-between; }}
            .section-head, .report-head {{ flex-direction:column; align-items:stretch; }}
            .section-actions {{ justify-content:stretch; }}
            .section-actions .tab {{ flex:1; }}
            .primary-action {{ width:100%; }}
            .toolbar {{ display:grid; grid-template-columns:1fr; }}
            .tabs {{ display:grid; grid-template-columns:repeat(2, minmax(0, 1fr)); }}
            .tab {{ width:100%; }}
            .index-head {{ flex-direction:column; }}
            .index-summary {{ grid-template-columns:1fr; }}
            button {{ width:100%; }}
            .grid, .status-grid, .wide, .ops-grid {{ grid-template-columns:1fr; }}
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
    {admin_bar_html()}
    <main class="page">
        <header class="topbar">
            <div>
                <h2>AI 客服 Dashboard</h2>
                <p class="subtitle">LINE 客服、FAQ、網站索引與回應品質總覽</p>
            </div>
            <label class="theme-control">
                <span>深夜模式</span>
                <span class="switch">
                    <input id="theme-toggle" type="checkbox" onchange="toggleTheme()">
                    <span class="slider"></span>
                </span>
            </label>
        </header>

        <nav class="nav">{nav_html("Dashboard")}</nav>
        {f'<div class="toast">{e(notice)}</div>' if notice else ''}

        <section class="status-grid">{status_cards}</section>

        <section class="section-head">
            <div>
                <h2>營運總覽</h2>
                <p class="subtitle">核心數字集中看，避免和明細資料混在一起。</p>
            </div>
            <div>
                <div class="label">統計期間</div>
                <div class="tabs section-actions">{time_tabs(days, chart).replace('/weekly-report', '/')}</div>
            </div>
        </section>
        <section class="grid">
            <div class="card">
                <div class="label">今日對話</div>
                <div class="value">{e(len(today_logs))}<span>筆</span></div>
            </div>
            <div class="card">
                <div class="label">{e(days_label(days))}對話</div>
                <div class="value">{e(len(report_logs))}<span>筆</span></div>
            </div>
            <div class="card">
                <div class="label">未回答 / 待修</div>
                <div class="value">{e(len(unanswered))}<span>筆</span></div>
            </div>
            <div class="card">
                <div class="label">平均延遲</div>
                <div class="value">{e(avg_latency)}<span>秒</span></div>
            </div>
            <div class="card">
                <div class="label">FAQ 總數</div>
                <div class="value">{e(len(faq))}<span>筆</span></div>
            </div>
            <div class="card">
                <div class="label">索引段落</div>
                <div class="value">{e(index_status.get("total_chunks", index_count()))}<span>段</span></div>
            </div>
            <div class="card">
                <div class="label">可能商機</div>
                <div class="value">{e(len(lead_logs))}<span>筆</span></div>
            </div>
            <div class="card">
                <div class="label">待人工追蹤</div>
                <div class="value">{e(len(pending_followups))}<span>筆</span></div>
            </div>
        </section>

        <section class="section-head">
            <div>
                <h2>回答與品質分析</h2>
                <p class="subtitle">同類資訊集中成圖表，快速看出來源、平台、品質與商機狀態。</p>
            </div>
            <div>
                <div class="label">圖表樣式</div>
                <div class="tabs section-actions">{chart_tabs(days, chart).replace('/weekly-report', '/')}</div>
            </div>
        </section>
        <section class="wide">
            <div class="card"><h3>平台分布</h3><div class="bar-chart">{platform_chart}</div></div>
            <div class="card"><h3>品牌/產品圖表</h3><div class="bar-chart">{brand_chart}</div></div>
            <div class="card"><h3>回答來源明細</h3><div class="bar-chart">{source_chart}</div></div>
            <div class="card"><h3>品質狀態</h3><div class="bar-chart">{quality_chart}</div></div>
            <div class="card"><h3>商機意圖</h3><div class="bar-chart">{lead_chart}</div></div>
        </section>

        <section class="ops-grid">
            <div class="card">
                <div class="index-head">
                    <div>
                        <div class="label">網站索引管理</div>
                        <p class="subtitle">網站索引狀態與各網站抓取結果集中在這裡。</p>
                    </div>
                    <div class="index-actions">
                        {('<span class="muted-pill">唯讀模式</span>' if readonly else '<form method="post" action="/dashboard/site-index/rebuild"><button>立即建立索引</button></form>')}
                    </div>
                </div>
                <div class="index-summary">
                    <div class="mini-stat">
                        <div class="label">最後更新</div>
                        <b>{e(index_status.get("last_run", "尚未建立"))}</b>
                    </div>
                    <div class="mini-stat">
                        <div class="label">索引段落數</div>
                        <b>{e(index_status.get("total_chunks", index_count()))} 段</b>
                    </div>
                </div>
                <table style="margin-top:14px;">
                    <tr><th>網站</th><th>網址</th><th>抓取頁數</th><th>索引段落</th><th>失敗</th></tr>
                    {site_rows}
                </table>
                {failure_html}
                <p class="subtitle">索引排程預設每 24 小時重建一次，也可以手動立即建立。</p>
            </div>

            <div class="card">
                <div class="label">健康檢查</div>
                <p class="subtitle">確認服務設定與必要資料檔是否存在。</p>
                <table style="margin-top:14px;">
                    <tr><th>項目</th><th>狀態</th></tr>
                    {health_rows}
                </table>
            </div>
        </section>

        <section class="section-head">
            <div>
                <h2>AI 客服週報與建議</h2>
            </div>
        </section>
        {report_html}
        <div class="card"><h3>重複問題</h3><table><tr><th>問題</th><th>次數</th></tr>{repeat_rows}</table></div>
        <script>
        (function(){{
            const savedTheme = localStorage.getItem("dashboard-theme");
            if(savedTheme === "dark"){{
                document.body.classList.add("dark");
            }}
        }})();

        document.addEventListener("DOMContentLoaded", function(){{
            const toggle = document.getElementById("theme-toggle");
            if(toggle){{
                toggle.checked = document.body.classList.contains("dark");
            }}
            const toast = document.querySelector(".toast");
            if(toast){{
                setTimeout(function(){{
                    toast.style.opacity = "0";
                    toast.style.transform = "translateY(-6px)";
                }}, 2600);
                setTimeout(function(){{ toast.remove(); }}, 3200);
            }}
        }});

        function toggleTheme(){{
            const toggle = document.getElementById("theme-toggle");
            const isDark = toggle ? toggle.checked : !document.body.classList.contains("dark");
            document.body.classList.toggle("dark", isDark);
            localStorage.setItem("dashboard-theme", isDark ? "dark" : "light");
        }}

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
    return RedirectResponse("/?notice=網站索引已開始建立，稍後可查看最後更新時間", status_code=302)
