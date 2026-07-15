from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response
import csv
import html
import io
import json
import os
from datetime import datetime, time
from urllib.parse import urlencode
from deepseek import ask_deepseek
from admin_ui import admin_bar_css, admin_bar_html
import admin_tools

router = APIRouter()

LOG_PATH = "logs/chat_logs.json"
FAQ_PATH = "data/faq.json"

NO_INFO_MARKERS = [
    "沒有相關資訊",
    "目前知識庫沒有",
    "目前網站索引沒有",
    "資料庫中沒有",
    "無法根據",
]


# =========================
# LOAD
# =========================
def load_logs():
    if not os.path.exists(LOG_PATH):
        return []

    try:
        with open(LOG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except:
        return []


def save_logs(data):
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def g(d, k, default="-"):
    return d.get(k, default) if isinstance(d, dict) else default


def e(value):
    return html.escape(str(value))


def source_summary(value):
    source = str(value or "-").strip()

    if source.startswith("網站索引 - "):
        rest = source.replace("網站索引 - ", "", 1)
        items = [item.strip() for item in rest.split(",") if item.strip()]
        count = len(dict.fromkeys(items))
        return f"網站索引 · {count} 項來源" if count else "網站索引"

    if source.startswith("http"):
        items = [item.strip() for item in source.split(",") if item.strip()]
        count = len(dict.fromkeys(items))
        return f"網站來源 · {count} 項" if count > 1 else "網站來源"

    if len(source) > 28:
        return source[:28] + "..."

    return source


def source_detail_html(value):
    source = str(value or "-").strip()

    if source.startswith("網站索引 - "):
        rest = source.replace("網站索引 - ", "", 1)
        items = list(dict.fromkeys([item.strip() for item in rest.split(",") if item.strip()]))

        if items:
            links = "".join(
                f'<a class="source-link" href="{e(item)}" target="_blank" rel="noopener noreferrer">{e(item)}</a>'
                if item.startswith("http") else f'<div class="source-link">{e(item)}</div>'
                for item in items
            )
            return f'<div class="source-list"><b>網站索引</b>{links}</div>'

    return f'<div class="detail-text">{e(source)}</div>'


def lead_badge(item):
    score = int(item.get("lead_score") or 0)
    need_followup = bool(item.get("need_followup"))
    intent = str(item.get("intent", "一般詢問"))

    if need_followup:
        return f'<span class="lead-badge hot">待追蹤 · {score}</span>'

    if score >= 35:
        return f'<span class="lead-badge warm">{e(intent)} · {score}</span>'

    return '<span class="lead-badge">一般</span>'


def contact_detail_html(item):
    fields = [
        ("姓名", item.get("contact_name", "")),
        ("公司", item.get("contact_company", "")),
        ("電話", item.get("contact_phone", "")),
        ("Email", item.get("contact_email", "")),
        ("需求", item.get("contact_need", "")),
    ]
    rows = "".join(
        f"<div><b>{e(label)}</b><span>{e(value or '-')}</span></div>"
        for label, value in fields
    )

    if not any(value for _, value in fields):
        return ""

    return f"""
    <div class="block">
        <span class="pill-more"><b>聯絡資料</b></span>
        <div class="contact-grid">{rows}</div>
    </div>
    """


def user_profile_html(item):
    platform = str(item.get("platform", "")).upper()

    if platform == "WEB":
        fields = [
            ("WEB Session ID", item.get("web_session_id", item.get("user", ""))),
            ("瀏覽器", item.get("browser", "")),
            ("裝置", item.get("device", "")),
            ("User Agent", item.get("user_agent", "")),
        ]
        rows = "".join(
            f"<div><b>{e(label)}</b><span>{e(value or '-')}</span></div>"
            for label, value in fields
        )
        return f"""
        <div class="block">
            <span class="pill-more"><b>WEB 訪客</b></span>
            <div class="line-profile">
                <div class="line-avatar empty">WEB</div>
                <div class="contact-grid">{rows}</div>
            </div>
        </div>
        """

    fields = [
        ("LINE 暱稱", item.get("line_display_name", "")),
        ("LINE User ID", item.get("line_user_id", item.get("user", ""))),
        ("語言", item.get("line_language", "")),
        ("狀態訊息", item.get("line_status_message", "")),
    ]
    rows = "".join(
        f"<div><b>{e(label)}</b><span>{e(value or '-')}</span></div>"
        for label, value in fields
    )
    avatar = item.get("line_picture_url", "")
    avatar_html = (
        f'<img class="line-avatar" src="{e(avatar)}" alt="LINE 使用者頭像">'
        if avatar else '<div class="line-avatar empty">LINE</div>'
    )

    if not any(value for _, value in fields):
        return ""

    return f"""
    <div class="block">
        <span class="pill-more"><b>LINE 使用者</b></span>
        <div class="line-profile">
            {avatar_html}
            <div class="contact-grid">{rows}</div>
        </div>
    </div>
    """


def image_detail_html(item):
    if item.get("attachment_type") != "image":
        return ""

    fields = [
        ("圖片路徑", item.get("attachment_path", "")),
        ("辨識內容", item.get("image_text", "")),
    ]
    rows = "".join(
        f"<div><b>{e(label)}</b><span>{e(value or '-')}</span></div>"
        for label, value in fields
    )

    return f"""
    <div class="block">
        <span class="pill-more"><b>圖片辨識</b></span>
        <div class="contact-grid">{rows}</div>
    </div>
    """


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


def load_faq_questions():
    if not os.path.exists(FAQ_PATH):
        return set()

    try:
        with open(FAQ_PATH, "r", encoding="utf-8") as f:
            faq = json.load(f)
    except:
        return set()

    return {
        str(item.get("question", "")).strip().lower()
        for item in faq
        if item.get("question")
    }


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


def parse_log_time(value):
    try:
        return datetime.strptime(str(value), "%Y/%m/%d %H:%M:%S")
    except:
        return None


def parse_date(value, end_of_day=False):
    if not value:
        return None

    try:
        date_value = datetime.strptime(value, "%Y-%m-%d").date()
        return datetime.combine(date_value, time.max if end_of_day else time.min)
    except:
        return None


def is_unanswered_log(item):
    reply = str(item.get("reply", ""))
    source = str(item.get("source", ""))
    quality = str(item.get("quality", ""))
    return (
        source == "AI客服"
        or quality in {"fix", "wrong"}
        or any(marker in reply for marker in NO_INFO_MARKERS)
    )


def filter_logs(
    logs,
    keyword="",
    platform="",
    source="",
    quick="",
    date_from="",
    date_to="",
    sort_by="time",
    sort_order="desc"
):
    if not isinstance(logs, list):
        logs = []

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

    if quick:
        faq_questions = load_faq_questions()

        if quick == "unanswered":
            logs = [l for l in logs if is_unanswered_log(l)]
        elif quick == "ai":
            logs = [l for l in logs if str(l.get("source", "")) in {"AI客服", "AI"}]
        elif quick == "faq":
            logs = [l for l in logs if str(l.get("source", "")) == "FAQ"]
        elif quick == "site-index":
            logs = [
                l for l in logs
                if "網站索引" in str(l.get("source", ""))
                or str(l.get("source", "")).startswith("http")
                or str(l.get("source", "")).startswith("URL-")
            ]
        elif quick == "transferred":
            logs = [
                l for l in logs
                if str(l.get("message", "")).strip().lower() in faq_questions
            ]
        elif quick == "needs-review":
            logs = [l for l in logs if str(l.get("quality", "")) in {"fix", "wrong"}]
        elif quick == "followup":
            logs = [l for l in logs if bool(l.get("need_followup")) and l.get("followup_status", "pending") == "pending"]

    start_at = parse_date(date_from)
    end_at = parse_date(date_to, end_of_day=True)

    if start_at or end_at:
        filtered = []

        for item in logs:
            log_time = parse_log_time(item.get("time", ""))

            if not log_time:
                continue

            if start_at and log_time < start_at:
                continue

            if end_at and log_time > end_at:
                continue

            filtered.append(item)

        logs = filtered

    sort_key = SORT_MAP.get(sort_by, "time")
    reverse = (sort_order == "desc")

    logs.sort(key=lambda x: x.get(sort_key, ""), reverse=reverse)
    return logs


def export_link(
    keyword="",
    platform="",
    source="",
    quick="",
    date_from="",
    date_to="",
    sort_by="time",
    sort_order="desc"
):
    params = {
        "keyword": keyword,
        "platform": platform,
        "source": source,
        "quick": quick,
        "date_from": date_from,
        "date_to": date_to,
        "sort_by": sort_by,
        "sort_order": sort_order,
    }
    query = urlencode({k: v for k, v in params.items() if v})
    return "/logs/export" + (f"?{query}" if query else "")


@router.get("/logs/export")
def export_logs(
    keyword: str = "",
    platform: str = "",
    source: str = "",
    quick: str = "",
    date_from: str = "",
    date_to: str = "",
    sort_by: str = "time",
    sort_order: str = "desc",
    notice: str = ""
):
    logs = filter_logs(load_logs(), keyword, platform, source, quick, date_from, date_to, sort_by, sort_order)

    output = io.StringIO()
    output.write("\ufeff")
    writer = csv.writer(output)
    writer.writerow(["ID", "時間", "平台", "問題", "回覆", "延遲", "來源", "商機意圖", "商機分數", "待追蹤", "IP"])

    for i, item in enumerate(logs):
        writer.writerow([
            g(item, "id", i + 1),
            g(item, "time"),
            g(item, "platform", "LINE"),
            g(item, "message", ""),
            g(item, "reply", ""),
            g(item, "latency", "-"),
            g(item, "source", "-"),
            g(item, "intent", "-"),
            g(item, "lead_score", 0),
            "是" if item.get("need_followup") else "否",
            g(item, "ip", "-"),
        ])

    filename = f"chat_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@router.post("/logs/quality/{log_id}")
def mark_quality(
    log_id: int,
    quality: str = Form(...),
    return_to: str = Form("/logs")
):
    allowed = {"good", "fix", "wrong"}
    logs = load_logs()

    if quality in allowed:
        for item in logs:
            if item.get("id") == log_id:
                item["quality"] = quality
                break
        save_logs(logs)

    if not return_to.startswith("/"):
        return_to = "/logs"

    return RedirectResponse(return_to, status_code=302)


@router.post("/logs/followup/{log_id}")
def mark_followup(
    log_id: int,
    status: str = Form(...),
    return_to: str = Form("/logs")
):
    allowed = {"pending", "done"}
    logs = load_logs()

    if status in allowed:
        for item in logs:
            if item.get("id") == log_id:
                item["followup_status"] = status
                item["need_followup"] = (status == "pending")
                break
        save_logs(logs)

    if not return_to.startswith("/"):
        return_to = "/logs"

    return RedirectResponse(return_to, status_code=302)


# =========================
# UI
# =========================
@router.get("/logs", response_class=HTMLResponse)
def logs_ui(
    request: Request,
    page: int = 1,
    size: int = 10,
    keyword: str = "",
    platform: str = "",
    source: str = "",
    quick: str = "",
    date_from: str = "",
    date_to: str = "",
    sort_by: str = "time",
    sort_order: str = "desc",
    notice: str = ""
):

    logs = filter_logs(load_logs(), keyword, platform, source, quick, date_from, date_to, sort_by, sort_order)
    readonly = admin_tools.is_readonly_admin(request)

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
    current_query = urlencode({
        "page": page,
        "size": size,
        "keyword": keyword,
        "platform": platform,
        "source": source,
        "quick": quick,
        "date_from": date_from,
        "date_to": date_to,
        "sort_by": sort_by,
        "sort_order": sort_order,
    })
    current_return_to = "/logs" + (f"?{current_query}" if current_query else "")

    # =========================
    # ROWS
    # =========================
    rows = ""
    faq_questions = load_faq_questions()

    for i, l in enumerate(logs_page):
        meta = l.get("meta", {}) if isinstance(l.get("meta"), dict) else {}
        message = g(l, "message", "")
        reply = g(l, "reply", "")
        source_value = g(l, "source", "-")
        log_id = g(l, "id", i + 1)
        quality = g(l, "quality", "")
        quality_text = {
            "good": "良好",
            "fix": "待修",
            "wrong": "錯誤",
        }.get(quality, "未標記")
        is_faq = str(message).strip().lower() in faq_questions
        if is_faq:
            transfer_html = '<span class="faq-added-pill">已轉 FAQ</span>'
        elif readonly:
            transfer_html = '<span class="faq-added-pill">唯讀</span>'
        else:
            transfer_html = f"""
                <form class="inline-form" method="post" action="/faq/add">
                    <input type="hidden" name="question" value="{e(message)}">
                    <input type="hidden" name="answer" value="{e(reply)}">
                    <input type="hidden" name="return_to" value="{e(current_return_to)}">
                    <button type="submit" class="faq-transfer-btn">轉 FAQ</button>
                </form>
            """

        # =========================
        # MAIN ROW
        # =========================
        rows += f"""
        <tr>
            <td data-label="ID">{e(log_id)}</td>
            <td data-label="時間" class="time">{e(g(l,'time'))}</td>
            <td data-label="平台"><span class="pill">{e(g(l,'platform','LINE'))}</span></td>

            <td data-label="問題" class="msg">{e(str(message)[:45])}</td>
            <td data-label="回覆" class="reply-cell">{e(str(reply)[:60])}</td>

            <td data-label="延遲" class="latency">{e(g(l,'latency','-'))}</td>
            <td data-label="來源" class="source"><span title="{e(source_value)}">{e(source_summary(source_value))}</span></td>
            <td data-label="商機" class="lead-cell">{lead_badge(l)}</td>
            <td data-label="IP" class="ip">{e(g(l,'ip','-'))}</td>

            <td data-label="更多資訊" class="log-actions">
                <button onclick="toggleDetail({i})">點擊查看</button>
                {transfer_html}
            </td>
        </tr>

        """

        # =========================
        # DETAIL ROW（在下一列）
        # =========================
        rows += f"""
        <tr id="detail-{i}" class="detail-row" style="display:none;">
            <td colspan="10">
                <div class="detail-box" id="detail-content-{i}">

                    <div class="grid">
                        <!-- 
                        <div><span class="pill-more"><b>DEVICE</b></span><br>{meta.get('device','-')}</div>
                        <div><span class="pill-more"><b>BROWSER</b></span><br>{meta.get('browser','-')}</div>
                        <div><span class="pill-more"><b>USER AGENT</b></span><br>{meta.get('user_agent','-')}</div>
                        <div><span class="pill-more"><b>來源</b></span><br>{g(l,'source','-')}</div>
                        <div><span class="pill-more"><b>IP</b></span><br>{g(l,'ip','-')}</div>
                        -->
                    </div>

                    <div class="block">
                        <span class="pill-more"><b>問題</b></span>
                        <div class="detail-text">{e(message)}</div>
                    </div>

                    <div class="block">
                        <span class="pill-more"><b>回覆</b></span>
                        <div class="detail-text">{e(reply)}</div>
                    </div>

                    <div class="block">
                        <span class="pill-more"><b>來源</b></span>
                        {source_detail_html(source_value)}
                    </div>

                    <div class="block">
                        <span class="pill-more"><b>商機 / 人工追蹤</b></span>
                        <div class="detail-text">
意圖：{e(g(l, 'intent', '一般詢問'))}
分數：{e(g(l, 'lead_score', 0))}
是否待追蹤：{e('是' if l.get('need_followup') else '否')}
狀態：{e(g(l, 'followup_status', 'none'))}
原因：{e(g(l, 'lead_reason', '-'))}
                        </div>
                        <form class="followup-form" method="post" action="/logs/followup/{e(log_id)}">
                            <input type="hidden" name="return_to" value="{e(current_return_to)}">
                            <button name="status" value="pending" class="quality-warn">待追蹤</button>
                            <button name="status" value="done">已處理</button>
                        </form>
                    </div>

                    {contact_detail_html(l)}
                    {user_profile_html(l)}
                    {image_detail_html(l)}

                    <div class="block">
                        <span class="pill-more"><b>品質</b></span>
                        <div class="quality-row">
                            <span class="quality-pill">{e(quality_text)}</span>
                            <form method="post" action="/logs/quality/{e(log_id)}">
                                <input type="hidden" name="return_to" value="{e(current_return_to)}">
                                <button name="quality" value="good">良好</button>
                                <button name="quality" value="fix" class="quality-warn">待修</button>
                                <button name="quality" value="wrong" class="quality-danger">錯誤</button>
                            </form>
                        </div>
                    </div>

                    <div class="block">
                        <a class="export-link" href="/logs/summary/{e(log_id)}" target="_blank">產生 AI 摘要</a>
                    </div>

                </div>
            </td>
        </tr>
        """

    # =========================
    # OPTIONS
    # =========================
    page_opts = [10, 20, 50]

    def link(p):
        query = urlencode({
            "page": p,
            "size": size,
            "keyword": keyword,
            "platform": platform,
            "source": source,
            "quick": quick,
            "date_from": date_from,
            "date_to": date_to,
            "sort_by": sort_by,
            "sort_order": sort_order,
        })
        return f"?{query}"

    pages = ""

    if page > 1:
        pages += f'<a href="{link(page-1)}">← 上一頁</a> '

    pages += f"<span class='info'>第 {page}/{total_pages} 頁 ｜ 總數 {total} ｜ 每頁 {size} 筆</span> "

    if page < total_pages:
        pages += f'<a href="{link(page+1)}">下一頁 →</a>'

    size_select = "".join(
        [f'<option value="{s}" {"selected" if s==size else ""}>{s} 筆</option>' for s in page_opts]
    )
    download_url = export_link(keyword, platform, source, quick, date_from, date_to, sort_by, sort_order)
    quick_items = [
        ("", "全部"),
        ("unanswered", "未回答"),
        ("ai", "AI 客服"),
        ("faq", "FAQ"),
        ("site-index", "網站索引"),
        ("transferred", "已轉 FAQ"),
        ("needs-review", "待修 / 錯誤"),
        ("followup", "待追蹤"),
    ]

    def quick_link(value):
        query = urlencode({
            "page": 1,
            "size": size,
            "keyword": keyword,
            "platform": platform,
            "source": source,
            "quick": value,
            "date_from": date_from,
            "date_to": date_to,
            "sort_by": sort_by,
            "sort_order": sort_order,
        })
        return "/logs" + (f"?{query}" if query else "")

    quick_buttons = "".join(
        f'<a class="quick-chip {"active" if quick == value else ""}" href="{e(quick_link(value))}">{label}</a>'
        for value, label in quick_items
    )

    # =========================
    # JS（只新增，不動架構）
    # =========================
    js = """
    <script>
    (function(){
        const savedTheme = localStorage.getItem("logs-theme");
        if(savedTheme === "dark"){
            document.body.classList.add("dark");
        }
    })();

    document.addEventListener("DOMContentLoaded", function(){
        const toggle = document.getElementById("theme-toggle");
        if(toggle){
            toggle.checked = document.body.classList.contains("dark");
        }
    });

    function toggleTheme(){
        const toggle = document.getElementById("theme-toggle");
        const isDark = toggle ? toggle.checked : !document.body.classList.contains("dark");
        document.body.classList.toggle("dark", isDark);
        localStorage.setItem("logs-theme", isDark ? "dark" : "light");
    }

    function toggleDetail(i){
        const content = document.getElementById("detail-content-" + i);
        const modal = document.getElementById("detail-modal");
        const body = document.getElementById("detail-modal-body");
        if(!content || !modal || !body) return;
        body.innerHTML = content.innerHTML;
        modal.style.display = "flex";
    }

    function closeModal(){
        const modal = document.getElementById("detail-modal");
        if(modal) modal.style.display = "none";
    }
    </script>
    """

    # =========================
    # CSS（完全不動，只補一點點）
    # =========================
    css = """
    :root {
        --bg: #f6f7fb;
        --panel: #ffffff;
        --panel-soft: #f1f5f9;
        --text: #172033;
        --muted: #64748b;
        --border: #e2e8f0;
        --accent: #4f46e5;
        --accent-strong: #3730a3;
        --accent-soft: #e0e7ff;
        --button-bg: linear-gradient(135deg,#60a5fa,#a78bfa);
        --button-bg-hover: linear-gradient(135deg,#3b82f6,#8b5cf6);
        --danger: #dc2626;
        --shadow: 0 16px 40px rgba(15, 23, 42, 0.08);
    }

    * {
        box-sizing: border-box;
    }

    body {
        margin:0;
        font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC";
        background:
            radial-gradient(circle at top left, rgba(96,165,250,0.14), transparent 30%),
            var(--bg);
        min-height:100vh;
        padding:24px;
        color:var(--text);
        font-size:16px;
        transition: background 0.2s ease, color 0.2s ease;
    }

    body.dark {
        --bg: #0f172a;
        --panel: #162033;
        --panel-soft: #1e293b;
        --text: #e5edf7;
        --muted: #94a3b8;
        --border: #334155;
        --accent: #93c5fd;
        --accent-strong: #c4b5fd;
        --accent-soft: rgba(96,165,250,0.18);
        --button-bg: linear-gradient(135deg,#60a5fa,#a78bfa);
        --button-bg-hover: linear-gradient(135deg,#3b82f6,#8b5cf6);
        --danger: #fb7185;
        --shadow: 0 16px 40px rgba(0, 0, 0, 0.28);
    }

    .page {
        max-width: 1280px;
        margin: 0 auto;
    }

    .nav {
        margin:0 0 18px;
    }

    .nav-menu {
        display:flex;
        gap:8px;
        flex-wrap:wrap;
    }

    .nav-toggle {
        display:none;
    }

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

    .nav-link.active {
        color:white;
        background:var(--button-bg);
        border:1px solid transparent;
    }

    .topbar {
        display:flex;
        align-items:flex-end;
        justify-content:space-between;
        gap:16px;
        margin-bottom:18px;
    }

    .title-block h2 {
        margin:0;
        font-size:28px;
        line-height:1.2;
        font-weight:700;
        letter-spacing:0;
    }

    .subtitle {
        margin:8px 0 0;
        color:var(--muted);
        font-size:13px;
    }

    .theme-control {
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
    }

    .switch {
        position:relative;
        width:52px;
        height:30px;
        flex:0 0 auto;
    }

    .switch input {
        position:absolute;
        opacity:0;
        width:0;
        height:0;
    }

    .slider {
        position:absolute;
        inset:0;
        border-radius:999px;
        background:#cbd5e1;
        transition:background 0.2s ease;
        box-shadow:inset 0 1px 3px rgba(15,23,42,0.18);
    }

    .slider::before {
        content:"";
        position:absolute;
        width:26px;
        height:26px;
        left:2px;
        top:2px;
        border-radius:50%;
        background:#ffffff;
        box-shadow:0 2px 8px rgba(15,23,42,0.25);
        transition:transform 0.2s ease;
    }

    .switch input:checked + .slider {
        background:linear-gradient(135deg,#60a5fa,#a78bfa);
    }

    .switch input:checked + .slider::before {
        transform:translateX(22px);
    }

    .switch input:focus-visible + .slider {
        outline:3px solid rgba(96,165,250,0.35);
        outline-offset:2px;
    }

    /* FILTER BAR */
    .bar {
        background:var(--panel);
        padding:16px;
        margin-bottom:16px;
        border-radius:8px;
        display:flex;
        gap:10px;
        flex-wrap:wrap;
        box-shadow:var(--shadow);
        border:1px solid var(--border);
    }

    .quick-filters {
        display:flex;
        gap:8px;
        flex-wrap:wrap;
        margin:0 0 16px;
    }

    .notice-card {
        background:#e0e7ff;
        border:1px solid #c7d2fe;
        color:#3730a3;
        border-radius:8px;
        box-shadow:var(--shadow);
        padding:14px 16px;
        margin-bottom:16px;
        font-weight:800;
    }

    .quick-chip {
        min-height:34px;
        padding:7px 11px;
        border-radius:999px;
        border:1px solid var(--border);
        background:var(--panel-soft);
        color:var(--muted);
        text-decoration:none;
        display:inline-flex;
        align-items:center;
        justify-content:center;
        font-size:13px;
        font-weight:700;
        box-shadow:none;
    }

    .quick-chip.active {
        color:var(--accent-strong);
        background:var(--accent-soft);
        border-color:rgba(96,165,250,0.35);
    }

    input, select {
        min-height:40px;
        padding:8px 12px;
        border-radius:8px;
        border:1px solid var(--border);
        background:var(--panel-soft);
        color:var(--text);
        outline:none;
        transition:0.2s;
        font-size:13px;
    }

    input {
        min-width:240px;
        flex:1 1 260px;
    }

    input[type="date"] {
        min-width:150px;
        flex:0 1 170px;
    }

    input:focus, select:focus {
        border-color:var(--accent);
        background:var(--panel);
    }

    button, .clear-link, .export-link {
        min-height:40px;
        padding:8px 14px;
        border-radius:8px;
        border:none;
        background:var(--button-bg);
        color:white;
        cursor:pointer;
        font-weight:600;
        font-size:13px;
        text-decoration:none;
        display:inline-flex;
        align-items:center;
        justify-content:center;
        transition: transform 0.15s ease, background 0.15s ease;
    }

    button:hover, .clear-link:hover, .export-link:hover {
        transform: translateY(-1px);
        background:var(--button-bg-hover);
    }

    .clear-link {
        background:var(--danger);
    }

    .export-link {
        color:var(--accent);
        background:var(--accent-soft);
        border:1px solid rgba(96,165,250,0.35);
    }

    .export-link:hover {
        color:white;
    }

    .inline-form {
        display:inline-flex;
        margin:0 0 0 6px;
    }

    .inline-form input {
        display:none;
    }

    .faq-transfer-btn {
        background:var(--accent-soft);
        color:var(--accent);
        border:1px solid rgba(96,165,250,0.35);
    }

    .faq-transfer-btn:hover {
        color:white;
        background:var(--button-bg-hover);
    }

    .faq-added-pill {
        min-height:36px;
        padding:7px 10px;
        border-radius:8px;
        display:inline-flex;
        align-items:center;
        justify-content:center;
        color:var(--accent-strong);
        background:var(--accent-soft);
        border:1px solid rgba(96,165,250,0.35);
        font-size:13px;
        font-weight:700;
        white-space:nowrap;
    }

    .log-actions {
        min-width:190px;
        display:flex;
        align-items:center;
        gap:8px;
        white-space:nowrap;
    }

    .log-actions .inline-form {
        margin:0;
    }

    .log-actions > button,
    .log-actions .inline-form button,
    .log-actions .faq-added-pill {
        min-width:82px;
        min-height:36px;
        padding:7px 10px;
        white-space:nowrap;
    }

    /* TABLE */
    .table-wrap {
        overflow-x:auto;
        border-radius:8px;
        box-shadow:var(--shadow);
        border:1px solid var(--border);
        background:var(--panel);
    }

    table {
        width:100%;
        border-collapse:collapse;
        background:var(--panel);
        overflow:hidden;
    }

    th {
        background:var(--panel-soft);
        padding:12px;
        text-align:left;
        font-size:13px;
        font-weight:700;
        color:var(--muted);
        white-space:nowrap;
    }

    td {
        padding:12px;
        border-top:1px solid var(--border);
        font-size:13px;
        vertical-align:top;
        color:var(--text);
    }

    tr:hover {
        background:var(--panel-soft);
    }

    .pill {
        padding:4px 10px;
        border-radius:999px;
        background:var(--accent-soft);
        color:var(--accent-strong);
        font-size:12px;
        font-weight:700;
    }
    
    .pill-more {
        padding:4px 10px;
        border-radius:999px;
        border: 1px solid var(--border);
        color:var(--muted);
        background:var(--panel);
    }

    .latency {
        color:var(--accent-strong);
        font-weight:700;
    }

    .msg {
        max-width:180px;
        line-height:1.5;
    }

    .reply-cell {
        max-width:220px;
        overflow:hidden;
        text-overflow:ellipsis;
        white-space:nowrap;
        color:var(--muted);
    }

    .source {
        font-weight:600;
        color:var(--accent-strong);
        white-space:nowrap;
    }

    .source span {
        display:inline-flex;
        max-width:130px;
        overflow:hidden;
        text-overflow:ellipsis;
        white-space:nowrap;
        vertical-align:top;
    }

    .ip {
        font-family:monospace;
        color:var(--muted);
    }

    .detail-box {
        margin:8px 0;
        padding:16px;
        background:var(--panel-soft);
        border-radius:8px;
        border:1px solid var(--border);
    }

    .grid {
        display:grid;
        grid-template-columns:repeat(3,1fr);
        gap:10px;
        font-size:12px;
        margin-bottom:10px;
    }

    .block {
        margin-top:10px;
        font-size:13px;
    }

    .detail-text {
        margin:12px 0 0 0;
        padding:12px;
        border-radius:8px;
        background:var(--panel);
        border:1px solid var(--border);
        line-height:1.7;
        white-space:pre-wrap;
    }

    .source-list {
        margin:12px 0 0 0;
        padding:12px;
        border-radius:8px;
        background:var(--panel);
        border:1px solid var(--border);
        line-height:1.7;
    }

    .source-list b {
        display:block;
        margin-bottom:8px;
    }

    .source-link {
        display:block;
        color:var(--accent-strong);
        text-decoration:none;
        overflow-wrap:anywhere;
        word-break:break-word;
        padding:7px 0;
        border-top:1px solid var(--border);
    }

    .source-link:first-of-type {
        border-top:none;
    }

    .lead-cell {
        min-width:92px;
    }

    .lead-badge {
        min-height:28px;
        padding:5px 8px;
        border-radius:999px;
        display:inline-flex;
        align-items:center;
        justify-content:center;
        background:var(--panel-soft);
        color:var(--muted);
        border:1px solid var(--border);
        font-size:12px;
        font-weight:800;
        white-space:nowrap;
    }

    .lead-badge.warm {
        background:#fef3c7;
        color:#92400e;
        border-color:#fde68a;
    }

    .lead-badge.hot {
        background:#fee2e2;
        color:#b91c1c;
        border-color:#fecaca;
    }

    .contact-grid {
        margin:12px 0 0 0;
        display:grid;
        grid-template-columns:repeat(2, minmax(0, 1fr));
        gap:10px;
    }

    .contact-grid div {
        padding:10px 12px;
        border-radius:8px;
        background:var(--panel);
        border:1px solid var(--border);
    }

    .contact-grid b {
        display:block;
        color:var(--muted);
        font-size:12px;
        margin-bottom:5px;
    }

    .contact-grid span {
        display:block;
        overflow-wrap:anywhere;
        line-height:1.6;
    }

    .line-profile {
        display:flex;
        align-items:flex-start;
        gap:14px;
        margin-top:12px;
    }

    .line-profile .contact-grid {
        flex:1;
        margin:0;
    }

    .line-avatar {
        width:56px;
        height:56px;
        border-radius:999px;
        object-fit:cover;
        border:1px solid var(--border);
        background:var(--panel-soft);
        flex:0 0 auto;
    }

    .line-avatar.empty {
        display:flex;
        align-items:center;
        justify-content:center;
        color:var(--accent-strong);
        font-size:12px;
        font-weight:900;
    }

    .quality-row {
        display:flex;
        gap:10px;
        flex-wrap:wrap;
        align-items:center;
        margin-top:12px;
    }

    .quality-row form {
        display:flex;
        gap:8px;
        flex-wrap:wrap;
    }

    .followup-form {
        display:flex;
        gap:8px;
        flex-wrap:wrap;
        margin-top:10px;
    }

    .quality-row button {
        min-height:34px;
        padding:7px 10px;
    }

    .followup-form button {
        min-height:34px;
        padding:7px 10px;
    }

    .quality-pill {
        min-height:34px;
        padding:7px 10px;
        border-radius:8px;
        display:inline-flex;
        align-items:center;
        background:var(--panel);
        border:1px solid var(--border);
        color:var(--muted);
        font-weight:700;
    }

    .quality-warn {
        background:#f59e0b;
    }

    .quality-danger {
        background:var(--danger);
    }

    .modal {
        position:fixed;
        inset:0;
        z-index:50;
        display:none;
        align-items:center;
        justify-content:center;
        padding:18px;
        background:rgba(15,23,42,0.55);
    }

    .modal-panel {
        width:min(760px, 100%);
        max-height:88vh;
        overflow:auto;
        background:var(--panel);
        border:1px solid var(--border);
        border-radius:8px;
        box-shadow:var(--shadow);
        padding:16px;
    }

    .modal-head {
        display:flex;
        align-items:center;
        justify-content:space-between;
        gap:12px;
        margin-bottom:12px;
    }

    .modal-head h3 {
        margin:0;
    }

    .pages {
        margin:14px 0;
        display:flex;
        gap:10px;
        align-items:center;
        flex-wrap:wrap;
        justify-content:center;
    }

    .pages a {
        padding:8px 12px;
        border-radius:8px;
        background:var(--panel);
        border:1px solid var(--border);
        text-decoration:none;
        color:var(--text);
        font-size: 12px;
    }

    .info {
        font-size:13px;
        color:var(--muted);
    }

    """ + admin_bar_css() + """

    @media (max-width: 760px) {
        body {
            padding:14px;
        }

        .topbar {
            align-items:stretch;
            flex-direction:column;
        }

        .title-block h2 {
            font-size:24px;
        }

        .theme-control {
            width:100%;
            justify-content:space-between;
        }

        .nav-toggle {
            display:flex;
            width:100%;
            min-height:40px;
            padding:8px 12px;
            border-radius:8px;
            border:1px solid var(--border);
            background:var(--panel);
            color:var(--text);
            font-weight:700;
            align-items:center;
            justify-content:space-between;
        }

        .nav-menu {
            display:none;
            grid-template-columns:1fr;
            gap:8px;
            margin-top:8px;
        }

        .nav.open .nav-menu {
            display:grid;
        }

        .nav-link {
            width:100%;
        }

        .bar {
            display:grid;
            grid-template-columns:1fr;
        }

        .quick-filters {
            display:grid;
            grid-template-columns:repeat(2, minmax(0, 1fr));
        }

        .quick-chip {
            width:100%;
        }

        input, select, button, .clear-link, .export-link {
            width:100%;
            min-width:0;
        }

        .table-wrap {
            overflow:visible;
            background:transparent;
            border:none;
            box-shadow:none;
        }

        table, tbody, tr, td {
            display:block;
            width:100%;
        }

        table {
            background:transparent;
        }

        tr:first-child {
            display:none;
        }

        tr {
            margin-bottom:12px;
            border:1px solid var(--border);
            border-radius:8px;
            background:var(--panel);
            box-shadow:var(--shadow);
            overflow:hidden;
        }

        tr.detail-row {
            margin-top:-12px;
            border-top:none;
            border-radius:0 0 8px 8px;
            box-shadow:none;
        }

        td {
            display:grid;
            grid-template-columns:92px minmax(0, 1fr);
            gap:10px;
            border-top:1px solid var(--border);
            padding:10px 12px;
        }

        td:first-child {
            border-top:none;
        }

        td::before {
            content:attr(data-label);
            color:var(--muted);
            font-weight:700;
        }

        .log-actions {
            display:grid;
            grid-template-columns:repeat(2, minmax(0, 1fr));
            gap:10px;
            min-width:0;
            align-items:stretch;
        }

        .log-actions::before {
            grid-column:1 / -1;
        }

        .log-actions > button,
        .log-actions .inline-form,
        .log-actions .inline-form button,
        .log-actions .faq-added-pill {
            width:100%;
            min-width:0;
        }

        .log-actions .inline-form {
            display:flex;
            margin:0;
        }

        .detail-row td {
            display:block;
        }

        .detail-row td::before {
            display:none;
        }

        .msg, .reply-cell {
            max-width:none;
            white-space:normal;
            overflow:visible;
            text-overflow:clip;
        }

        .source,
        .source span {
            max-width:none;
            white-space:normal;
            overflow:visible;
            text-overflow:clip;
        }

        .line-profile {
            flex-direction:column;
        }

        .line-profile .contact-grid {
            width:100%;
        }

        .contact-grid {
            grid-template-columns:1fr;
        }
    }
    """

    return HTMLResponse(f"""
    <html>
    <head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1"/>
    <script>
    (function(){{
        var theme = localStorage.getItem("admin-theme")
            || localStorage.getItem("logs-theme")
            || "light";
        if(theme === "dark"){{
            document.documentElement.classList.add("dark");
        }}
    }})();
    </script>
    <style>{css}</style>
    </head>

    <body>
    {admin_bar_html()}
    <main class="page">

    <header class="topbar">
        <div class="title-block">
            <h2>LOGS管理介面</h2>
            <p class="subtitle">LINE 對話紀錄、來源與回應時間</p>
        </div>
        <label class="theme-control">
            <span>深夜模式</span>
            <span class="switch">
                <input id="theme-toggle" type="checkbox" onchange="toggleTheme()">
                <span class="slider"></span>
            </span>
        </label>
    </header>

    <nav class="nav">{nav_html("LOGS")}</nav>
    {f'<section class="notice-card">{e(notice)}</section>' if notice else ''}

    <div class="quick-filters">{quick_buttons}</div>

    <form class="bar">
        <input type="hidden" name="quick" value="{e(quick)}">
        <input name="keyword" value="{e(keyword)}" placeholder="關鍵字">
        <input type="date" name="date_from" value="{e(date_from)}" title="開始日期">
        <input type="date" name="date_to" value="{e(date_to)}" title="結束日期">

        <select name="size">
            {size_select}
        </select>

        <select name="sort_by">
            <option value="time">時間</option>
            <option value="latency">回應時間</option>
            <option value="source">來源</option>
        </select>

        <select name="sort_order">
            <option value="desc">DESC</option>
            <option value="asc">ASC</option>
        </select>

        <a href="/logs" class="clear-link">清空</a>
        <a href="{e(download_url)}" class="export-link">匯出 CSV</a>
        
        <button>搜尋</button>
    </form>

    <div class="pages">{pages}</div>

    <div class="table-wrap">
    <table>
        <tr>
            <th width="3%">ID</th>
            <th width="12%">時間</th>
            <th width="5%">平台</th>
            <th width="14%">問題</th>
            <th width="14%">回覆</th>
            <th width="5%">延遲</th>
            <th width="8%">來源</th>
            <th width="7%">商機</th>
            <th width="8%">IP</th>
            <th width="5%">更多資訊</th>
        </tr>

        {rows}
    </table>
    </div>

    <div class="pages">{pages}</div>
    </main>

    <div class="modal" id="detail-modal" onclick="if(event.target.id === 'detail-modal') closeModal()">
        <div class="modal-panel">
            <div class="modal-head">
                <h3>對話詳情</h3>
                <button type="button" onclick="closeModal()">關閉</button>
            </div>
            <div id="detail-modal-body"></div>
        </div>
    </div>

    {js}

    </body>
    </html>
    """)


@router.get("/logs/summary/{log_id}", response_class=HTMLResponse)
def log_summary(log_id: int):
    target = None

    for item in load_logs():
        if item.get("id") == log_id:
            target = item
            break

    if not target:
        return HTMLResponse("<h2>找不到這筆 LOG</h2>", status_code=404)

    prompt = """
你是客服主管，請根據以下單筆客服 LOG 產生繁體中文摘要。
請輸出：
1. 使用者意圖
2. 回答是否足夠
3. 建議補充的 FAQ 或知識庫方向
4. 建議下一步
請簡潔、條列、不要誇大。
"""
    user_message = f"""
問題：
{target.get("message", "")}

回答：
{target.get("reply", "")}

來源：
{target.get("source", "")}
"""

    try:
        summary = ask_deepseek(prompt, user_message)
    except Exception as exc:
        summary = f"摘要產生失敗：{exc}"

    return HTMLResponse(f"""
    <html>
    <head>
    <meta charset="utf-8"/>
    <meta name="viewport" content="width=device-width, initial-scale=1"/>
    <style>
    body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC"; background:#f6f7fb; color:#172033; padding:24px; }}
    .page {{ max-width:900px; margin:0 auto; }}
    .card {{ background:white; border:1px solid #e2e8f0; border-radius:8px; padding:16px; box-shadow:0 16px 40px rgba(15,23,42,0.08); margin-bottom:14px; }}
    .text {{ white-space:pre-wrap; line-height:1.7; }}
    {admin_bar_css()}
    </style>
    </head>
    <body>{admin_bar_html()}<main class="page">
    <div class="card"><h2>LOG #{e(log_id)} AI 摘要</h2></div>
    <div class="card"><div class="text">{e(summary)}</div></div>
    </main></body></html>
    """)
