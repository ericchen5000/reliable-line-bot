import sqlite3
from urllib.parse import quote_plus

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from core.config import DB_PATH

router = APIRouter()


@router.get("/logs", response_class=HTMLResponse)
def view_logs(
    request: Request,
    page: int = 1,
    q: str = "",
    channel: str = "",
    sort_by: str = "created_at",
    sort_order: str = "desc"
):

    allowed_sort_fields = {
        "id": "id",
        "created_at": "created_at",
        "channel": "channel",
        "response_time": "response_time"
    }

    sort_by_sql = allowed_sort_fields.get(sort_by, "created_at")
    sort_order_sql = "ASC" if str(sort_order).lower() == "asc" else "DESC"

    per_page = 30
    if page < 1:
        page = 1
    offset = (page - 1) * per_page

    where_clauses = []
    params = []

    # =========================
    # SEARCH
    # =========================
    if q.strip():
        where_clauses.append("""
        (
            user_question LIKE ?
            OR ai_reply LIKE ?
            OR used_sources LIKE ?
            OR user_ip LIKE ?
            OR session_id LIKE ?
        )
        """)
        keyword = f"%{q.strip()}%"
        params.extend([keyword, keyword, keyword, keyword, keyword])

    if channel.strip():
        where_clauses.append("channel = ?")
        params.append(channel.strip())

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # =========================
    # COUNT
    # =========================
    count_sql = f"""
    SELECT COUNT(*)
    FROM chat_logs
    {where_sql}
    """
    cur.execute(count_sql, params)
    total_rows = cur.fetchone()[0]

    # =========================
    # QUERY
    # =========================
    query_sql = f"""
    SELECT
        id,
        session_id,
        user_question,
        ai_reply,
        used_sources,
        created_at,
        user_ip,
        channel,
        response_time
    FROM chat_logs
    {where_sql}
    ORDER BY {sort_by_sql} {sort_order_sql}
    LIMIT ? OFFSET ?
    """

    cur.execute(query_sql, params + [per_page, offset])
    rows = cur.fetchall()

    conn.close()

    total_pages = max(1, (total_rows + per_page - 1) // per_page)

    # =========================
    # ROW HTML
    # =========================
    html_rows = ""

    for r in rows:
        row_id = r[0]
        session_id = r[1] or ""
        question = r[2] or ""
        reply = r[3] or ""
        sources = r[4] or "—"
        created_at = r[5] or ""
        user_ip = r[6] or ""
        row_channel = r[7] or "web"
        response_time = r[8]

        response_time_text = f"{response_time}s" if response_time is not None else "—"

        question_short = question[:60] + "..." if len(question) > 60 else question
        reply_short = reply[:120] + "..." if len(reply) > 120 else reply

        html_rows += f"""
        <tr>
            <td class="col-id">{row_id}</td>
            <td class="col-time">{created_at}</td>

            <td class="col-channel">
                <span class="badge badge-channel">{row_channel}</span>
            </td>

            <td class="col-question">
                <div class="question-text">{question_short}</div>
            </td>

            <td class="col-reply">
                <div class="reply-text">{reply_short}</div>
            </td>

            <td class="col-response-time">
                {response_time_text}
            </td>

            <td class="col-source">
                <div class="source-text">{sources}</div>
            </td>

            <td class="col-ip">{user_ip}</td>

            <td class="col-action">
                <details class="detail-box">
                    <summary>展開</summary>

                    <div class="detail-content">

                        <div class="detail-block">
                            <div class="detail-label">Session ID</div>
                            <div class="detail-value">{session_id}</div>
                        </div>

                        <div class="detail-block">
                            <div class="detail-label">完整問題</div>
                            <div class="detail-value">{question}</div>
                        </div>

                        <div class="detail-block">
                            <div class="detail-label">完整回覆</div>
                            <div class="detail-value">{reply}</div>
                        </div>

                        <div class="detail-grid">
                            <div class="detail-block">
                                <div class="detail-label">平台</div>
                                <div class="detail-value">{row_channel}</div>
                            </div>

                            <div class="detail-block">
                                <div class="detail-label">回應時間</div>
                                <div class="detail-value">{response_time_text}</div>
                            </div>
                        </div>

                    </div>
                </details>
            </td>
        </tr>
        """

    # =========================
    # HTML
    # =========================
    html = f"""
    <!doctype html>
    <html lang="zh-Hant">
    <head>
      <meta charset="utf-8">
      <meta name="viewport" content="width=device-width, initial-scale=1">
      <title>Logs</title>

      <style>
        body {{
          margin: 0;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Noto Sans TC", sans-serif;
          background: #f5f7fb;
          color: #111827;
          padding: 24px;
        }}

        h1 {{
          margin: 0 0 16px 0;
          font-size: 28px;
        }}

        .card {{
          background: white;
          border-radius: 16px;
          padding: 16px;
          box-shadow: 0 6px 20px rgba(0,0,0,0.06);
          margin-bottom: 16px;
        }}

        input, select {{
          padding: 10px 12px;
          border-radius: 999px;
          border: 1px solid #e5e7eb;
          background: #f9fafb;
          margin-right: 8px;
        }}

        .btn {{
          padding: 10px 16px;
          border-radius: 999px;
          border: none;
          background: linear-gradient(135deg,#60a5fa,#a78bfa);
          color: white;
          cursor: pointer;
        }}

        table {{
          width: 100%;
          border-collapse: collapse;
          background: white;
          border-radius: 16px;
          overflow: hidden;
        }}

        th {{
          text-align: left;
          background: #f3f4f6;
          padding: 12px;
          font-size: 13px;
        }}

        td {{
          padding: 12px;
          border-top: 1px solid #eee;
          font-size: 13px;
          vertical-align: top;
        }}

        .badge {{
          padding: 4px 10px;
          border-radius: 999px;
          background: #e0f2fe;
          font-size: 12px;
        }}

        .badge-channel {{
          background: #dcfce7;
        }}

        .col-response-time {{
          font-weight: 700;
          color: #16a34a;
        }}

        .question-text {{
          font-weight: 600;
        }}

        .reply-text {{
          color: #374151;
        }}

        .detail-box summary {{
          cursor: pointer;
          padding: 6px 10px;
          border-radius: 999px;
          background: #2563eb;
          color: white;
          font-size: 12px;
        }}

        .detail-content {{
          margin-top: 10px;
          background: #f9fafb;
          padding: 12px;
          border-radius: 12px;
        }}

        .detail-label {{
          font-size: 12px;
          color: #6b7280;
          margin-top: 8px;
        }}

        .detail-value {{
          margin-bottom: 8px;
        }}

      </style>
    </head>

    <body>

    <h1>Logs Dashboard</h1>

    <form method="get" class="card">
        <input name="q" placeholder="關鍵字搜尋" value="{q}">
        <input name="channel" placeholder="平台 (LINE/Web/FB)" value="{channel}">

        <select name="sort_order">
            <option value="desc">最新</option>
            <option value="asc">最舊</option>
        </select>

        <button class="btn">搜尋</button>
    </form>

    <div class="card">
    <table>
        <tr>
            <th>ID</th>
            <th>時間</th>
            <th>平台</th>
            <th>問題</th>
            <th>回覆</th>
            <th>回應時間</th>
            <th>來源</th>
            <th>IP</th>
            <th>操作</th>
        </tr>

        {html_rows}
    </table>
    </div>

    </body>
    </html>
    """

    return HTMLResponse(html)