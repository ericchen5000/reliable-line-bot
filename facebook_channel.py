"""Messenger webhook adapter; credentials are supplied only through environment variables."""
import asyncio
import hashlib
import hmac
import json
import logging
import os
import re
import sqlite3
import time
from types import SimpleNamespace
from contextlib import contextmanager

import requests
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse

logger = logging.getLogger(__name__)


def create_facebook_router(answer, context, normalize, classify, handoff, save_log):
    router = APIRouter()
    page_id = os.getenv('FB_PAGE_ID', '').strip()
    token = os.getenv('FB_PAGE_ACCESS_TOKEN', '').strip()
    secret = os.getenv('FB_APP_SECRET', '').strip()
    verify = os.getenv('FB_VERIFY_TOKEN', '').strip()
    version = os.getenv('FB_GRAPH_VERSION', '').strip()
    enabled = os.getenv('FB_AUTO_REPLY', 'false').lower() == 'true'
    db_path = os.getenv('FB_QUEUE_PATH', 'logs/facebook_queue.sqlite3')
    worker_task = None

    @contextmanager
    def db():
        os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
        con = sqlite3.connect(db_path, timeout=10)
        con.execute('CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, payload TEXT NOT NULL, state TEXT NOT NULL DEFAULT \'pending\', attempts INTEGER NOT NULL DEFAULT 0, next_at REAL NOT NULL DEFAULT 0, created REAL NOT NULL)')
        try:
            with con:
                yield con
        finally:
            con.close()

    @router.get('/webhook')
    async def verify_webhook(request: Request):
        q = request.query_params
        if not verify:
            raise HTTPException(503, 'FB_VERIFY_TOKEN 尚未設定')
        if q.get('hub.mode') != 'subscribe' or not hmac.compare_digest(q.get('hub.verify_token', ''), verify):
            raise HTTPException(403, 'Webhook 驗證失敗')
        challenge = q.get('hub.challenge')
        if not challenge:
            raise HTTPException(400, '缺少 challenge')
        return PlainTextResponse(challenge)

    @router.post('/webhook')
    async def receive(request: Request):
        if not all([page_id, token, secret, verify]) or not re.fullmatch(r'v\d+\.\d+', version):
            raise HTTPException(503, 'Facebook 設定尚未完成')
        body = await request.body()
        expected = 'sha256=' + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(request.headers.get('x-hub-signature-256', ''), expected):
            raise HTTPException(403, 'Webhook 簽章無效')
        try:
            payload = json.loads(body)
            if not isinstance(payload, dict) or not isinstance(payload.get('entry', []), list):
                raise ValueError()
            if payload.get('object') != 'page':
                return PlainTextResponse('EVENT_RECEIVED')
            events = []
            for entry in payload.get('entry', []):
                if str(entry.get('id')) != page_id:
                    continue
                for event in entry.get('messaging', []):
                    message = event.get('message', {})
                    sender = str(event.get('sender', {}).get('id', ''))
                    if not sender or sender == page_id or message.get('is_echo'):
                        continue
                    if str(event.get('recipient', {}).get('id')) != page_id:
                        continue
                    # Only reply to user messages; delivery/read/postback events are ignored.
                    if not message.get('mid') or not (message.get('text') or message.get('attachments')):
                        continue
                    if enabled:
                        events.append((str(message['mid']), json.dumps(event), min(time.time(), float(event.get('timestamp', 0)) / 1000) if event.get('timestamp') else time.time()))
        except (ValueError, TypeError, AttributeError):
            raise HTTPException(400, 'Webhook 格式錯誤')
        # Commit before acknowledging Meta, so a process restart does not lose messages.
        def enqueue():
            with db() as con:
                con.executemany('INSERT OR IGNORE INTO events(id,payload,created) VALUES(?,?,?)', events)
        await asyncio.to_thread(enqueue)
        return PlainTextResponse('EVENT_RECEIVED')

    def process(row):
        event_id, raw, state, attempts, _, created = row
        event = json.loads(raw)
        sender = str(event['sender']['id'])
        user = 'fb:' + page_id + ':' + sender
        message = event['message']
        text = str(message.get('text', '')).strip()
        started = time.time()
        if text:
            entries = context(user)
            query = normalize(text, entries)
            reply, source = answer(text, search_message=query)
        else:
            text = '使用者傳送附件'
            query = text
            entries = []
            reply, source = '目前 Facebook 客服先支援文字問答，請用文字描述您的問題，或聯絡專人協助。', 'FB'
        lead = classify(text, reply, source)
        reply = handoff(reply, lead)
        # One bounded message avoids partially delivered multi-message replies.
        outgoing = f'{reply}\n\n資料來源：{source}'
        if len(outgoing) > 1900:
            outgoing = outgoing[:1850] + '\n（內容較長，請縮小問題範圍或聯絡專人。）'
        try:
            response = requests.post(
                f'https://graph.facebook.com/{version}/{page_id}/messages',
                headers={'Authorization': 'Bearer ' + token},
                json={'recipient': {'id': sender}, 'messaging_type': 'RESPONSE', 'message': {'text': outgoing}},
                timeout=(5, 25),
            )
        except requests.RequestException:
            # Delivery is ambiguous after a connection failure: do not auto-send twice.
            with db() as con:
                con.execute("UPDATE events SET state='uncertain' WHERE id=?", (event_id,))
            logger.error('FB delivery uncertain; inspect queue event %s before retrying', event_id)
            return
        if response.status_code >= 400:
            # Do not log response bodies or exceptions containing access credentials.
            with db() as con:
                con.execute("UPDATE events SET state='failed' WHERE id=?", (event_id,))
            logger.error('FB send failed HTTP %s for event %s', response.status_code, event_id)
            return
        with db() as con:
            con.execute("UPDATE events SET state='sent' WHERE id=?", (event_id,))
        request = SimpleNamespace(headers={}, client=SimpleNamespace(host='-'))
        try:
            save_log(user, text, reply, request, 'FB', round(time.time()-started, 3), source, lead,
                     {'fb_user_id': sender, 'fb_page_id': page_id, 'fb_message_id': event_id,
                      'search_message': query, 'context_used': query != text, 'context_turns': len(entries)})
        except Exception:
            logger.error('FB reply sent but conversation log failed for event %s', event_id)

    def next_event():
        with db() as con:
            con.execute("BEGIN IMMEDIATE")
            row = con.execute("SELECT * FROM events WHERE state='pending' AND next_at<=? ORDER BY created LIMIT 1", (time.time(),)).fetchone()
            if row:
                # Persist before sending: a crash during delivery requires manual review.
                con.execute("UPDATE events SET state='processing', attempts=attempts+1 WHERE id=?", (row[0],))
            return row

    async def worker():
        # Remain stopped until explicitly enabled; missing credentials cannot start sends.
        if not enabled or not all([page_id, token, secret, verify]) or not re.fullmatch(r'v\d+\.\d+', version):
            return
        while True:
            try:
                row = await asyncio.to_thread(next_event)
                if row:
                    if time.time() - row[5] > 23 * 3600:
                        with db() as con:
                            con.execute("UPDATE events SET state='expired' WHERE id=?", (row[0],))
                    else:
                        try:
                            await asyncio.to_thread(process, row)
                        except Exception:
                            with db() as con:
                                con.execute("UPDATE events SET state='failed' WHERE id=?", (row[0],))
                            logger.error('FB processing failed for event %s', row[0])
                else:
                    await asyncio.sleep(1)
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.error('FB queue unavailable')
                await asyncio.sleep(5)

    @router.on_event('startup')
    async def start():
        nonlocal worker_task
        worker_task = asyncio.create_task(worker())

    @router.on_event('shutdown')
    async def stop():
        if worker_task:
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass

    return router
