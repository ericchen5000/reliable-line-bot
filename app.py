from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from linebot import LineBotApi, WebhookHandler
from linebot.models import TextSendMessage

from config import LINE_CHANNEL_ACCESS_TOKEN, LINE_CHANNEL_SECRET
from routers.chat import ai_reply
from core.db import get_logs

app = FastAPI(title="AI Chat Enterprise System")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# -----------------------------
# health check
# -----------------------------
@app.get("/")
def home():
    return {"status": "ok"}

# -----------------------------
# LINE webhook
# -----------------------------
@app.post("/line/webhook")
async def webhook(request: Request):

    body = await request.json()

    if "events" not in body:
        raise HTTPException(status_code=400)

    for event in body["events"]:

        if event.get("type") != "message":
            continue

        if event["message"]["type"] != "text":
            continue

        user_msg = event["message"]["text"]

        reply = ai_reply(user_msg)

        line_bot_api.reply_message(
            event["replyToken"],
            TextSendMessage(text=reply)
        )

    return {"status": "ok"}

# -----------------------------
# logs API
# -----------------------------
@app.get("/logs")
def logs(limit: int = 50, keyword: str = None):

    data = get_logs(limit)

    if keyword:
        keyword = keyword.lower()
        data = [
            row for row in data
            if keyword in str(row).lower()
        ]

    return {
        "status": "ok",
        "count": len(data),
        "data": [
            {
                "user": row[0],
                "message": row[1],
                "reply": row[2],
                "time": row[3]
            }
            for row in data
        ]
    }

# -----------------------------
# UI: logs dashboard
# -----------------------------
@app.get("/ui/logs", response_class=HTMLResponse)
def logs_ui():

    return """
    <html>
    <head>
        <title>AI Logs Dashboard</title>
        <style>
            body { font-family: Arial; background:#f4f4f4; padding:20px; }
            table { border-collapse: collapse; width:100%; background:white; }
            th, td { border:1px solid #ddd; padding:8px; font-size:14px; }
            th { background:#333; color:white; }
        </style>
    </head>
    <body>
        <h2>AI Logs Dashboard</h2>
        <div id="data">Loading...</div>

        <script>
        async function loadLogs(){
            const res = await fetch('/logs');
            const json = await res.json();

            let html = '<table><tr><th>User</th><th>Message</th><th>Reply</th><th>Time</th></tr>';

            json.data.forEach(row => {
                html += `<tr>
                    <td>${row.user}</td>
                    <td>${row.message}</td>
                    <td>${row.reply}</td>
                    <td>${row.time}</td>
                </tr>`;
            });

            html += '</table>';
            document.getElementById('data').innerHTML = html;
        }

        loadLogs();
        setInterval(loadLogs, 3000);
        </script>
    </body>
    </html>
    """
