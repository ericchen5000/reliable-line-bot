from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import json
import os

app = FastAPI()

DB_PATH = "data.db"
LOG_PATH = "logs/chat_logs.json"
FAQ_FILE = "data/faq.json"


# =========================
# LOG VIEW
# =========================
@app.get("/logs", response_class=HTMLResponse)
def logs():
    if not os.path.exists(LOG_PATH):
        return HTMLResponse("<h1>No Logs</h1>")

    with open(LOG_PATH, "r", encoding="utf-8") as f:
        logs = json.load(f)

    html = "<h1>LOGS</h1><hr>"

    for l in reversed(logs):
        html += f"""
        <div>
            <b>User:</b> {l.get('user','')}<br>
            <b>Msg:</b> {l.get('message','')}<br>
            <b>Reply:</b> {l.get('reply','')}<br>
        </div>
        <hr>
        """

    return HTMLResponse(html)


# =========================
# FAQ VIEW
# =========================
@app.get("/faq", response_class=HTMLResponse)
def faq():

    if not os.path.exists(FAQ_FILE):
        return HTMLResponse("<h1>No FAQ</h1>")

    with open(FAQ_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    html = "<h1>FAQ</h1><hr>"

    for item in data:
        html += f"""
        <div>
            Q: {item.get('question','')}<br>
            A: {item.get('answer','')}<br>
        </div>
        <hr>
        """

    return HTMLResponse(html)