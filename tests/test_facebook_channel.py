import hashlib
import hmac
import json
import os
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient
from facebook_channel import create_facebook_router


class MessengerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = self.tmp.name + '/queue.sqlite3'
        self.env = patch.dict(os.environ, {'FB_PAGE_ID': '123', 'FB_PAGE_ACCESS_TOKEN': 'test-token',
            'FB_APP_SECRET': 'test-secret', 'FB_VERIFY_TOKEN': 'test-verify',
            'FB_GRAPH_VERSION': 'v99.0', 'FB_AUTO_REPLY': 'true', 'FB_QUEUE_PATH': self.path})
        self.env.start()
        self.logs = []

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def app(self):
        app = FastAPI()
        app.include_router(create_facebook_router(lambda *a, **k: ('answer', 'FAQ'), lambda u: [],
            lambda text, entries: text, lambda *a: {}, lambda reply, lead: reply,
            lambda *a: self.logs.append(a)))
        return app

    def payload(self, **changes):
        message = {'mid': 'm1', 'text': 'question'}
        message.update(changes)
        return {'object': 'page', 'entry': [{'id': '123', 'messaging': [{'sender': {'id': '456'},
            'recipient': {'id': '123'}, 'timestamp': int(time.time()*1000), 'message': message}]}]}

    def send(self, client, payload):
        body = json.dumps(payload).encode()
        sig = 'sha256=' + hmac.new(b'test-secret', body, hashlib.sha256).hexdigest()
        return client.post('/webhook', content=body, headers={'x-hub-signature-256': sig})

    def test_verification_and_missing_signature(self):
        with TestClient(self.app()) as client:
            self.assertEqual(client.get('/webhook', params={'hub.mode': 'subscribe',
                'hub.verify_token': 'test-verify', 'hub.challenge': '987'}).text, '987')
            self.assertEqual(client.get('/webhook', params={'hub.mode': 'subscribe',
                'hub.verify_token': 'wrong', 'hub.challenge': '987'}).status_code, 403)
            self.assertEqual(client.post('/webhook', json=self.payload()).status_code, 403)
            self.assertEqual(self.send(client, {'entry': 'bad'}).status_code, 400)

    @patch('facebook_channel.requests.post')
    def test_reply_and_dedup(self, post):
        post.return_value.status_code = 200
        with TestClient(self.app()) as client:
            self.assertEqual(self.send(client, self.payload()).status_code, 200)
            self.send(client, self.payload())
            time.sleep(1.3)
        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args.kwargs['json']['recipient']['id'], '456')
        self.assertEqual(self.logs[0][4], 'FB')
        self.assertEqual(self.logs[0][0], 'fb:123:456')
        with sqlite3.connect(self.path) as con:
            self.assertEqual(con.execute('SELECT state FROM events').fetchone()[0], 'sent')
        # Reopening the application must not resend an already delivered event.
        with TestClient(self.app()) as client:
            self.send(client, self.payload())
            time.sleep(.1)
        self.assertEqual(post.call_count, 1)

    @patch('facebook_channel.requests.post')
    def test_ignore_echo_wrong_page_and_disabled(self, post):
        with TestClient(self.app()) as client:
            self.send(client, self.payload(is_echo=True))
            other = self.payload(); other['entry'][0]['id'] = '999'
            self.send(client, other)
            time.sleep(.1)
        self.assertFalse(post.called)
        os.environ['FB_AUTO_REPLY'] = 'false'
        with TestClient(self.app()) as client:
            self.send(client, self.payload())
        with sqlite3.connect(self.path) as con:
            self.assertEqual(con.execute('SELECT COUNT(*) FROM events').fetchone()[0], 0)

    @patch('facebook_channel.requests.post')
    def test_send_failure_not_logged_as_success(self, post):
        post.return_value.status_code = 400
        with TestClient(self.app()) as client:
            self.send(client, self.payload())
            time.sleep(1.3)
        self.assertFalse(self.logs)
        with sqlite3.connect(self.path) as con:
            self.assertEqual(con.execute('SELECT state FROM events').fetchone()[0], 'failed')

    @patch('facebook_channel.requests.post')
    def test_attachment_and_old_message(self, post):
        post.return_value.status_code = 200
        with TestClient(self.app()) as client:
            self.send(client, self.payload(text='', attachments=[{'type': 'image'}]))
            old = self.payload(mid='old'); old['entry'][0]['messaging'][0]['timestamp'] -= 25*3600*1000
            self.send(client, old)
            time.sleep(1.3)
        self.assertEqual(post.call_count, 1)
        self.assertIn('文字', post.call_args.kwargs['json']['message']['text'])
        with sqlite3.connect(self.path) as con:
            self.assertEqual(con.execute("SELECT state FROM events WHERE id='old'").fetchone()[0], 'expired')

    @patch('facebook_channel.requests.post')
    def test_network_uncertainty_not_retried(self, post):
        import requests
        post.side_effect = requests.Timeout()
        with TestClient(self.app()) as client:
            self.send(client, self.payload())
            time.sleep(1.3)
            self.send(client, self.payload())
            time.sleep(.1)
        self.assertEqual(post.call_count, 1)
        with sqlite3.connect(self.path) as con:
            self.assertEqual(con.execute('SELECT state FROM events').fetchone()[0], 'uncertain')

if __name__ == '__main__':
    unittest.main()
