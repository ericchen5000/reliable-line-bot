from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
import html
import json
import os

from services.search_index import INDEX_FILE, load_status, build_all_indexes

router = APIRouter()


def e(value):
    return html.escape(str(value))


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


def index_count():
    if not os.path.exists(INDEX_FILE):
        return 0

    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as f:
            return len(json.load(f))
    except:
        return 0


@router.get("/site-index", response_class=HTMLResponse)
def site_index_page():
    status = load_status()
    sites = status.get("sites", [])

    rows = ""
    for site in sites:
        rows += f"""
        <tr>
            <td>{e(site.get("title", "-"))}</td>
            <td>{e(site.get("url", "-"))}</td>
            <td>{e(site.get("chunks", 0))}</td>
        </tr>
        """

    if not rows:
        rows = """
        <tr>
            <td colspan="3">尚未建立索引</td>
        </tr>
        """

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
        .page {{
            max-width:1280px;
            margin:0 auto;
        }}
        .topbar {{
            display:flex;
            align-items:flex-end;
            justify-content:space-between;
            gap:16px;
            margin-bottom:18px;
        }}
        .nav {{
            display:flex;
            gap:8px;
            flex-wrap:wrap;
            margin:0 0 18px;
        }}
        .nav-link {{
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
        }}
        .nav-link.active {{
            color:white;
            background:var(--button-bg);
            border:none;
        }}
        .card {{
            background:var(--panel);
            padding:16px;
            border:1px solid var(--border);
            border-radius:8px;
            box-shadow:var(--shadow);
            margin-bottom:16px;
        }}
        h2 {{
            margin:0;
            font-size:28px;
        }}
        .subtitle {{
            margin:8px 0 0;
            color:var(--muted);
            font-size:13px;
        }}
        .muted {{
            color:#64748b;
            font-size:13px;
        }}
        button, a {{
            min-height:40px;
            padding:8px 14px;
            border-radius:8px;
            border:none;
            color:white;
            background:var(--button-bg);
            text-decoration:none;
            font-weight:700;
            cursor:pointer;
            display:inline-flex;
            align-items:center;
        }}
        table {{
            width:100%;
            border-collapse:collapse;
        }}
        th, td {{
            padding:12px;
            border-top:1px solid var(--border);
            text-align:left;
            vertical-align:top;
        }}
        th {{
            color:var(--muted);
            background:var(--panel-soft);
        }}
        @media (max-width:860px) {{
            body {{ padding:14px; }}
            h2 {{ font-size:24px; }}
            .topbar {{ flex-direction:column; align-items:stretch; }}
            .nav-link {{ width:100%; justify-content:center; }}
            table, tbody, tr, td {{ display:block; width:100%; }}
            tr {{ border:1px solid var(--border); border-radius:8px; overflow:hidden; margin-bottom:12px; background:var(--panel); }}
            tr:first-child {{ display:none; }}
            td {{ border-top:1px solid var(--border); }}
        }}
    </style>
    </head>
    <body>
    <main class="page">
        <header class="topbar">
            <div>
                <h2>網站索引管理</h2>
                <p class="subtitle">管理指定網站的本地搜尋索引</p>
            </div>
        </header>
        <nav class="nav">{nav_html("網站索引")}</nav>
        <div class="card">
            <p class="muted">索引會依照 data/urls.json 的網站清單建立。排程預設每 24 小時重建一次。</p>
            <p>最後更新：{e(status.get("last_run", "尚未建立"))}</p>
            <p>目前索引段落數：{e(status.get("total_chunks", index_count()))}</p>
            <form method="post" action="/site-index/rebuild">
                <button>立即重建索引</button>
            </form>
        </div>

        <div class="card">
            <table>
                <tr>
                    <th>網站</th>
                    <th>網址</th>
                    <th>索引段落</th>
                </tr>
                {rows}
            </table>
        </div>
    </main>
    </body>
    </html>
    """)


@router.post("/site-index/rebuild")
def rebuild_site_index(background_tasks: BackgroundTasks):
    background_tasks.add_task(build_all_indexes)
    return RedirectResponse("/site-index", status_code=302)
