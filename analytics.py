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
    .grid { display:grid; grid-template-columns:repeat(4, minmax(0, 1fr)); gap:14px; margin-bottom:14px; }
    .wide { display:grid; grid-template-columns:1fr 1fr; gap:14px; }
    .card { background:var(--panel); border:1px solid var(--border); border-radius:8px; box-shadow:var(--shadow); padding:16px; margin-bottom:14px; }
    .label { color:var(--muted); font-size:13px; font-weight:700; }
    .value { margin-top:8px; font-size:28px; font-weight:800; }
    table { width:100%; border-collapse:collapse; }
    th, td { padding:12px; border-top:1px solid var(--border); text-align:left; vertical-align:top; line-height:1.6; }
    th { color:var(--muted); background:var(--panel-soft); }
    .pill { display:inline-flex; min-height:30px; align-items:center; padding:5px 9px; border-radius:999px; background:var(--accent-soft); color:var(--accent); font-size:13px; font-weight:800; }
    @media (max-width:860px) { body { padding:14px; } h2 { font-size:24px; } .grid,.wide { grid-template-columns:1fr; } .nav-link { width:100%; } table,tbody,tr,td { display:block; width:100%; } tr { border:1px solid var(--border); border-radius:8px; overflow:hidden; margin-bottom:12px; background:var(--panel); } tr:first-child { display:none; } td { display:grid; grid-template-columns:90px 1fr; gap:10px; } td::before { content:attr(data-label); color:var(--muted); font-weight:700; } }
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


@router.get("/weekly-report", response_class=HTMLResponse)
def weekly_report():
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

    return HTMLResponse(f"""
    <html><head><meta charset="utf-8"/><style>{base_css()}</style></head>
    <body><main class="page">
    <header class="topbar"><h2>AI 客服週報</h2><p class="subtitle">最近 7 天客服營運摘要</p></header>
    <nav class="nav">{nav_html("週報")}</nav>
    <section class="grid">
        <div class="card"><div class="label">7 天對話</div><div class="value">{len(logs)}</div></div>
        <div class="card"><div class="label">未回答 / 待修</div><div class="value">{len(unanswered)}</div></div>
        <div class="card"><div class="label">FAQ 總數</div><div class="value">{len(faq)}</div></div>
        <div class="card"><div class="label">索引段落</div><div class="value">{e(index_status.get("total_chunks", 0))}</div></div>
    </section>
    <section class="wide">
        <div class="card"><h3>資料來源分布</h3><table><tr><th>來源</th><th>次數</th></tr>{source_rows}</table></div>
        <div class="card"><h3>品牌/產品熱度</h3><table><tr><th>品牌</th><th>提及次數</th></tr>{brand_rows}</table></div>
    </section>
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
