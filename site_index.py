from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
import html
import json
import os

from services.search_index import INDEX_FILE, load_status, build_all_indexes

router = APIRouter()


def e(value):
    return html.escape(str(value))


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
        body {{
            margin:0;
            font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC";
            background:#f6f7fb;
            padding:24px;
            color:#172033;
        }}
        .page {{
            max-width:960px;
            margin:0 auto;
        }}
        .card {{
            background:white;
            padding:16px;
            border:1px solid #e2e8f0;
            border-radius:8px;
            box-shadow:0 16px 40px rgba(15,23,42,0.08);
            margin-bottom:16px;
        }}
        h2 {{
            margin:0 0 8px;
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
            background:linear-gradient(135deg,#60a5fa,#a78bfa);
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
            border-top:1px solid #e2e8f0;
            text-align:left;
            vertical-align:top;
        }}
        th {{
            color:#64748b;
            background:#f1f5f9;
        }}
    </style>
    </head>
    <body>
    <main class="page">
        <div class="card">
            <h2>網站索引管理</h2>
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
