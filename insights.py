from collections import Counter, defaultdict
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
import html
import json
import os

router = APIRouter()

LOG_PATH = "logs/chat_logs.json"
FAQ_PATH = "data/faq.json"


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


def nav_html(active=""):
    items = [
        ("/", "Dashboard"),
        ("/logs", "LOGS"),
        ("/faq", "FAQ"),
        ("/weekly-report", "週報"),
        ("/knowledge-gaps", "知識缺口"),
        ("/test-chat", "測試"),
        ("/health", "健康檢查"),
    ]
    return "".join(
        f'<a class="nav-link {"active" if active == label else ""}" href="{href}">{label}</a>'
        for href, label in items
    )


def base_css():
    return """
    :root {
        --bg:#f6f7fb;
        --panel:#ffffff;
        --panel-soft:#f1f5f9;
        --text:#172033;
        --muted:#64748b;
        --border:#e2e8f0;
        --accent:#4f46e5;
        --accent-soft:#e0e7ff;
        --danger:#dc2626;
        --button-bg:linear-gradient(135deg,#60a5fa,#a78bfa);
        --shadow:0 16px 40px rgba(15,23,42,0.08);
    }
    * { box-sizing:border-box; }
    body {
        margin:0;
        font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC";
        background:radial-gradient(circle at top left, rgba(96,165,250,0.14), transparent 30%), var(--bg);
        color:var(--text);
        padding:24px;
    }
    .page { max-width:1280px; margin:0 auto; }
    .topbar { margin-bottom:18px; }
    h2 { margin:0; font-size:28px; }
    .subtitle { color:var(--muted); font-size:13px; margin:8px 0 0; }
    .nav { display:flex; gap:8px; flex-wrap:wrap; margin:0 0 18px; }
    .nav-link {
        min-height:36px;
        padding:8px 12px;
        border-radius:8px;
        background:var(--panel);
        border:1px solid var(--border);
        color:var(--text);
        text-decoration:none;
        font-size:13px;
        font-weight:700;
        display:inline-flex;
        align-items:center;
        justify-content:center;
    }
    .nav-link.active { color:white; background:var(--button-bg); border:none; }
    .card {
        background:var(--panel);
        border:1px solid var(--border);
        border-radius:8px;
        box-shadow:var(--shadow);
        padding:16px;
        margin-bottom:14px;
    }
    table { width:100%; border-collapse:collapse; }
    th, td { padding:12px; border-top:1px solid var(--border); text-align:left; vertical-align:top; line-height:1.6; }
    th { background:var(--panel-soft); color:var(--muted); }
    button {
        min-height:36px;
        padding:7px 12px;
        border:none;
        border-radius:8px;
        background:var(--button-bg);
        color:white;
        font-weight:700;
        cursor:pointer;
    }
    input, textarea {
        width:100%;
        padding:10px 12px;
        border:1px solid var(--border);
        border-radius:8px;
        background:var(--panel-soft);
        color:var(--text);
        margin-bottom:8px;
    }
    textarea { min-height:96px; resize:vertical; }
    .muted { color:var(--muted); }
    @media (max-width:860px) {
        body { padding:14px; }
        h2 { font-size:24px; }
        table, tbody, tr, td { display:block; width:100%; }
        tr { border:1px solid var(--border); border-radius:8px; overflow:hidden; margin-bottom:12px; background:var(--panel); }
        tr:first-child { display:none; }
        td { display:grid; grid-template-columns:90px 1fr; gap:10px; }
        td::before { content:attr(data-label); color:var(--muted); font-weight:700; }
    }
    """


def faq_questions():
    return {
        str(item.get("question", "")).strip().lower()
        for item in load_json(FAQ_PATH, [])
        if item.get("question")
    }


def looks_unanswered(item):
    reply = str(item.get("reply", ""))
    source = str(item.get("source", ""))
    markers = ["沒有相關資訊", "目前知識庫沒有", "資料庫中沒有", "不知道"]
    return any(marker in reply for marker in markers) or source == "AI客服"


@router.get("/unanswered", response_class=HTMLResponse)
def unanswered_page():
    rows = ""
    for item in load_json(LOG_PATH, []):
        if not looks_unanswered(item):
            continue
        rows += f"""
        <tr>
            <td data-label="時間">{e(item.get("time", "-"))}</td>
            <td data-label="問題">{e(item.get("message", ""))}</td>
            <td data-label="回覆">{e(item.get("reply", ""))}</td>
            <td data-label="操作">
                <form method="post" action="/faq/add">
                    <input type="hidden" name="question" value="{e(item.get("message", ""))}">
                    <input type="hidden" name="answer" value="">
                    <input type="hidden" name="return_to" value="/unanswered">
                    <button>轉 FAQ 草稿</button>
                </form>
            </td>
        </tr>
        """

    if not rows:
        rows = "<tr><td colspan='4'>目前沒有未回答問題</td></tr>"

    return HTMLResponse(f"""
    <html><head><meta charset="utf-8"/><style>{base_css()}</style></head>
    <body><main class="page">
    <header class="topbar"><h2>未回答問題</h2><p class="subtitle">整理 AI 沒有把握回答的 LOGS</p></header>
    <nav class="nav">{nav_html("未回答")}</nav>
    <div class="card"><table>
    <tr><th>時間</th><th>問題</th><th>回覆</th><th>操作</th></tr>
    {rows}
    </table></div>
    </main></body></html>
    """)


@router.get("/faq-suggestions", response_class=HTMLResponse)
def faq_suggestions_page():
    logs = load_json(LOG_PATH, [])
    known = faq_questions()
    counts = Counter()
    samples = defaultdict(str)

    for item in logs:
        question = str(item.get("message", "")).strip()
        if not question or question.lower() in known:
            continue
        key = question.lower()
        counts[key] += 1
        samples[key] = question

    rows = ""
    for key, count in counts.most_common(30):
        if count < 2:
            continue
        question = samples[key]
        rows += f"""
        <tr>
            <td data-label="次數">{e(count)}</td>
            <td data-label="建議問題">{e(question)}</td>
            <td data-label="操作">
                <form method="post" action="/faq/add">
                    <input type="hidden" name="question" value="{e(question)}">
                    <input type="hidden" name="answer" value="">
                    <input type="hidden" name="return_to" value="/faq-suggestions">
                    <button>加入 FAQ 草稿</button>
                </form>
            </td>
        </tr>
        """

    if not rows:
        rows = "<tr><td colspan='3'>目前沒有重複問題建議</td></tr>"

    return HTMLResponse(f"""
    <html><head><meta charset="utf-8"/><style>{base_css()}</style></head>
    <body><main class="page">
    <header class="topbar"><h2>建議 FAQ</h2><p class="subtitle">從重複出現的 LOGS 問題整理建議</p></header>
    <nav class="nav">{nav_html("建議 FAQ")}</nav>
    <div class="card"><table>
    <tr><th>次數</th><th>建議問題</th><th>操作</th></tr>
    {rows}
    </table></div>
    </main></body></html>
    """)
