from collections import Counter, defaultdict
from datetime import datetime, timedelta
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
import html
import json
import os

router = APIRouter()

LOG_PATH = "logs/chat_logs.json"
FAQ_PATH = "data/faq.json"
INDEX_STATUS_PATH = "data/site_index_status.json"

BRANDS = [
    "Array Networks",
    "Array",
    "Vates",
    "Stratus",
    "Neverfail",
    "Penguin",
    "VMware",
    "Shadow AI",
    "Citrix",
]

NO_INFO_MARKERS = [
    "沒有相關資訊",
    "目前知識庫沒有",
    "目前網站索引沒有",
    "資料庫中沒有",
    "無法根據",
]


def e(value):
    return html.escape(str(value))


def load_json(path, default):
    if not os.path.exists(path):
        return default

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, type(default)) else default
    except:
        return default


def parse_time(value):
    try:
        return datetime.strptime(str(value), "%Y/%m/%d %H:%M:%S")
    except:
        return None


def nav_html(active=""):
    items = [
        ("/", "Dashboard"),
        ("/logs", "LOGS"),
        ("/faq", "FAQ"),
        ("/site-index", "網站索引"),
        ("/weekly-report", "週報"),
        ("/knowledge-gaps", "知識缺口"),
        ("/brand-heat", "品牌熱度"),
        ("/test-chat", "測試"),
        ("/health", "健康檢查"),
    ]
    return "".join(
        f'<a class="nav-link {"active" if active == label else ""}" href="{href}">{label}</a>'
        for href, label in items
    )


def base_css():
    return """
    :root { --bg:#f6f7fb; --panel:#fff; --panel-soft:#f1f5f9; --text:#172033; --muted:#64748b; --border:#e2e8f0; --accent:#4f46e5; --accent-soft:#e0e7ff; --button-bg:linear-gradient(135deg,#60a5fa,#a78bfa); --danger:#dc2626; --shadow:0 16px 40px rgba(15,23,42,0.08); }
    * { box-sizing:border-box; }
    body { margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC"; background:radial-gradient(circle at top left, rgba(96,165,250,0.14), transparent 30%), var(--bg); color:var(--text); padding:24px; font-size:16px; }
    .page { max-width:1280px; margin:0 auto; }
    .topbar { margin-bottom:18px; }
    h2 { margin:0; font-size:28px; }
    .subtitle { color:var(--muted); font-size:13px; margin:8px 0 0; }
    .nav { display:flex; gap:8px; flex-wrap:wrap; margin:0 0 18px; }
    .nav-link { min-height:36px; padding:8px 12px; border-radius:8px; background:var(--panel); border:1px solid var(--border); color:var(--text); text-decoration:none; font-size:13px; font-weight:700; display:inline-flex; align-items:center; justify-content:center; }
    .nav-link.active { color:white; background:var(--button-bg); border:none; }
    .report-top { display:flex; align-items:flex-end; justify-content:space-between; gap:14px; }
    .primary-action, .report-box button { min-height:40px; padding:8px 14px; border-radius:8px; border:none; background:var(--button-bg); color:white; cursor:pointer; font-weight:700; font-size:13px; text-decoration:none; display:inline-flex; align-items:center; justify-content:center; }
    .grid { display:grid; grid-template-columns:repeat(4, minmax(0, 1fr)); gap:14px; margin-bottom:14px; }
    .wide { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
    .card { background:var(--panel); border:1px solid var(--border); border-radius:8px; box-shadow:var(--shadow); padding:16px; margin-bottom:14px; }
    .label { color:var(--muted); font-size:13px; font-weight:700; }
    .value { margin-top:8px; font-size:28px; font-weight:800; }
    table { width:100%; border-collapse:collapse; }
    th, td { padding:12px; border-top:1px solid var(--border); text-align:left; vertical-align:top; line-height:1.6; }
    th { color:var(--muted); background:var(--panel-soft); }
    .pill { display:inline-flex; min-height:30px; align-items:center; padding:5px 9px; border-radius:999px; background:var(--accent-soft); color:var(--accent); font-size:13px; font-weight:800; }
    .bar-chart { display:grid; gap:12px; }
    .bar-row { display:grid; grid-template-columns:120px 1fr 42px; gap:10px; align-items:center; }
    .bar-name { color:var(--text); font-size:13px; font-weight:700; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .bar-track { height:12px; border-radius:999px; background:var(--panel-soft); overflow:hidden; border:1px solid var(--border); }
    .bar-fill { height:100%; border-radius:999px; background:var(--button-bg); min-width:8px; }
    .bar-count { color:var(--accent); font-weight:800; font-size:13px; text-align:right; }
    .empty-chart { color:var(--muted); padding:12px; border:1px dashed var(--border); border-radius:8px; background:var(--panel-soft); }
    .report-box { background:var(--panel); border:1px solid var(--border); border-radius:8px; box-shadow:var(--shadow); padding:16px; margin-bottom:14px; }
    .report-head { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:12px; }
    .report-head h3 { margin:0; }
    .report-text { padding:14px; border-radius:8px; background:var(--panel-soft); border:1px solid var(--border); white-space:pre-wrap; line-height:1.8; }
    @media (max-width:860px) { body { padding:14px; } h2 { font-size:24px; } .report-top,.report-head { align-items:stretch; flex-direction:column; } .primary-action,.report-box button { width:100%; } .grid,.wide { grid-template-columns:1fr; } .nav-link { width:100%; } .bar-row { grid-template-columns:1fr 64px; } .bar-name { grid-column:1 / -1; white-space:normal; } table,tbody,tr,td { display:block; width:100%; } tr { border:1px solid var(--border); border-radius:8px; overflow:hidden; margin-bottom:12px; background:var(--panel); } tr:first-child { display:none; } td { display:grid; grid-template-columns:90px 1fr; gap:10px; } td::before { content:attr(data-label); color:var(--muted); font-weight:700; } }
    """


def recent_logs(days=7):
    logs = load_json(LOG_PATH, [])
    since = datetime.now() - timedelta(days=days)
    return [
        item for item in logs
        if parse_time(item.get("time", "")) and parse_time(item.get("time", "")) >= since
    ]


def is_unanswered(item):
    reply = str(item.get("reply", ""))
    source = str(item.get("source", ""))
    quality = str(item.get("quality", ""))
    return (
        source == "AI客服"
        or quality in {"fix", "wrong"}
        or any(marker in reply for marker in NO_INFO_MARKERS)
    )


def repeated_questions(logs, min_count=2):
    counts = Counter(str(item.get("message", "")).strip() for item in logs if item.get("message"))
    return [(question, count) for question, count in counts.most_common(20) if count >= min_count]


def brand_counter(logs):
    counts = Counter()

    for item in logs:
        text = f"{item.get('message', '')} {item.get('reply', '')}".lower()
        for brand in BRANDS:
            if brand.lower() in text:
                counts[brand] += 1

    return counts


def bar_chart(items, empty_text="尚無資料"):
    items = list(items)

    if not items:
        return f"<div class='empty-chart'>{empty_text}</div>"

    max_count = max(count for _, count in items) or 1
    rows = []

    for label, count in items:
        width = round(count / max_count * 100, 1)
        rows.append(f"""
        <div class="bar-row">
            <div class="bar-name">{e(label)}</div>
            <div class="bar-track"><div class="bar-fill" style="width:{width}%"></div></div>
            <div class="bar-count">{count}</div>
        </div>
        """)

    return "".join(rows)


def weekly_report_text(total, unanswered_count, faq_count, chunks, sources, brands, repeats):
    top_source = sources.most_common(1)[0] if sources else ("尚無", 0)
    top_brand = brands.most_common(1)[0] if brands else ("尚無", 0)
    top_repeat = repeats[0] if repeats else ("尚無明顯重複問題", 0)
    action = "優先補強知識庫缺口，並把重複問題轉成 FAQ。"

    if total and unanswered_count / total < 0.15:
        action = "整體回答穩定，可持續補充高頻品牌與產品資料。"

    return f"""
本週 AI 客服共處理 {total} 筆對話，其中未回答或待修 {unanswered_count} 筆。

主要回答來源為「{top_source[0]}」，共 {top_source[1]} 筆。最常被提到的品牌/產品是「{top_brand[0]}」，共 {top_brand[1]} 次。

目前 FAQ 共 {faq_count} 筆，網站索引段落共 {chunks} 段。重複問題最高的是「{top_repeat[0]}」，出現 {top_repeat[1]} 次。

建議下一步：{action}
"""


@router.get("/weekly-report", response_class=HTMLResponse)
def weekly_report(generate: int = 0):
    logs = recent_logs(7)
    faq = load_json(FAQ_PATH, [])
    index_status = load_json(INDEX_STATUS_PATH, {})
    sources = Counter(str(item.get("source", "-")) for item in logs)
    unanswered = [item for item in logs if is_unanswered(item)]
    brands = brand_counter(logs)
    repeats = repeated_questions(logs)

    source_rows = "".join(
        f"<tr><td data-label='來源'>{e(source)}</td><td data-label='次數'>{count}</td></tr>"
        for source, count in sources.most_common(8)
    ) or "<tr><td colspan='2'>尚無資料</td></tr>"
    brand_rows = "".join(
        f"<tr><td data-label='品牌'>{e(brand)}</td><td data-label='提及次數'>{count}</td></tr>"
        for brand, count in brands.most_common(8)
    ) or "<tr><td colspan='2'>尚無品牌資料</td></tr>"
    repeat_rows = "".join(
        f"<tr><td data-label='問題'>{e(question)}</td><td data-label='次數'>{count}</td></tr>"
        for question, count in repeats[:8]
    ) or "<tr><td colspan='2'>尚無重複問題</td></tr>"
    source_chart = bar_chart(sources.most_common(8))
    brand_chart = bar_chart(brands.most_common(8), "尚無品牌資料")
    report_text = weekly_report_text(
        len(logs),
        len(unanswered),
        len(faq),
        index_status.get("total_chunks", 0),
        sources,
        brands,
        repeats,
    )
    report_html = f"""
    <section class="report-box" id="generated-report">
        <div class="report-head">
            <div>
                <h3>本週 AI 客服摘要</h3>
                <p class="subtitle">系統依最近 7 天 LOGS 自動整理</p>
            </div>
            <button type="button" onclick="navigator.clipboard.writeText(document.getElementById('report-text').innerText)">複製週報</button>
        </div>
        <div class="report-text" id="report-text">{e(report_text)}</div>
    </section>
    """ if generate else ""

    return HTMLResponse(f"""
    <html><head><meta charset="utf-8"/><style>{base_css()}</style></head>
    <body><main class="page">
    <header class="topbar report-top">
        <div><h2>AI 客服週報</h2><p class="subtitle">最近 7 天客服營運摘要</p></div>
        <a class="primary-action" href="/weekly-report?generate=1">一鍵產生週報</a>
    </header>
    <nav class="nav">{nav_html("週報")}</nav>
    {report_html}
    <section class="grid">
        <div class="card"><div class="label">7 天對話</div><div class="value">{len(logs)}</div></div>
        <div class="card"><div class="label">未回答 / 待修</div><div class="value">{len(unanswered)}</div></div>
        <div class="card"><div class="label">FAQ 總數</div><div class="value">{len(faq)}</div></div>
        <div class="card"><div class="label">索引段落</div><div class="value">{e(index_status.get("total_chunks", 0))}</div></div>
    </section>
    <section class="wide">
        <div class="card"><h3>資料來源圖表</h3><div class="bar-chart">{source_chart}</div></div>
        <div class="card"><h3>品牌/產品圖表</h3><div class="bar-chart">{brand_chart}</div></div>
    </section>
    <section class="wide">
        <div class="card"><h3>資料來源分布</h3><table><tr><th>來源</th><th>次數</th></tr>{source_rows}</table></div>
        <div class="card"><h3>品牌/產品熱度</h3><table><tr><th>品牌</th><th>提及次數</th></tr>{brand_rows}</table></div>
    </section>
    <script>
    if (window.location.search.includes("generate=1")) {{
        setTimeout(() => document.getElementById("generated-report")?.scrollIntoView({{behavior:"smooth", block:"start"}}), 120);
    }}
    </script>
    <div class="card"><h3>重複問題</h3><table><tr><th>問題</th><th>次數</th></tr>{repeat_rows}</table></div>
    </main></body></html>
    """)


@router.get("/knowledge-gaps", response_class=HTMLResponse)
def knowledge_gaps():
    logs = load_json(LOG_PATH, [])
    groups = defaultdict(lambda: {"count": 0, "latest": "-", "sample": ""})

    for item in logs:
        if not is_unanswered(item):
            continue
        question = str(item.get("message", "")).strip()
        if not question:
            continue
        key = question.lower()
        groups[key]["count"] += 1
        groups[key]["latest"] = item.get("time", "-")
        groups[key]["sample"] = question

    rows = "".join(
        f"<tr><td data-label='問題'>{e(data['sample'])}</td><td data-label='次數'>{data['count']}</td><td data-label='最近時間'>{e(data['latest'])}</td><td data-label='建議'><span class='pill'>補 FAQ / KB</span></td></tr>"
        for _, data in sorted(groups.items(), key=lambda kv: kv[1]["count"], reverse=True)[:50]
    ) or "<tr><td colspan='4'>目前沒有明顯知識缺口</td></tr>"

    return HTMLResponse(f"""
    <html><head><meta charset="utf-8"/><style>{base_css()}</style></head>
    <body><main class="page">
    <header class="topbar"><h2>知識庫缺口分析</h2><p class="subtitle">找出 AI 常答不好或資料不足的問題</p></header>
    <nav class="nav">{nav_html("知識缺口")}</nav>
    <div class="card"><table><tr><th>問題</th><th>次數</th><th>最近時間</th><th>建議</th></tr>{rows}</table></div>
    </main></body></html>
    """)


@router.get("/brand-heat", response_class=HTMLResponse)
def brand_heat():
    logs = load_json(LOG_PATH, [])
    counts = brand_counter(logs)
    total = sum(counts.values()) or 1
    rows = "".join(
        f"<tr><td data-label='品牌'>{e(brand)}</td><td data-label='提及次數'>{count}</td><td data-label='占比'>{round(count / total * 100, 1)}%</td></tr>"
        for brand, count in counts.most_common()
    ) or "<tr><td colspan='3'>尚無品牌熱度資料</td></tr>"

    return HTMLResponse(f"""
    <html><head><meta charset="utf-8"/><style>{base_css()}</style></head>
    <body><main class="page">
    <header class="topbar"><h2>產品 / 品牌熱度排行</h2><p class="subtitle">依 LOGS 自動統計客戶關注品牌</p></header>
    <nav class="nav">{nav_html("品牌熱度")}</nav>
    <div class="card"><table><tr><th>品牌</th><th>提及次數</th><th>占比</th></tr>{rows}</table></div>
    </main></body></html>
    """)
