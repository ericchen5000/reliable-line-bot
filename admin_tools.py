import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime, timedelta

from config import LINE_CHANNEL_SECRET


ADMIN_USERS_PATH = "data/admin_users.json"
ADMIN_ACTIVITY_PATH = "logs/admin_activity.json"
ADMIN_SESSIONS_PATH = "logs/admin_sessions.json"
AUTH_COOKIE = "reliable_admin"
ADMIN_SESSION_COOKIE = "reliable_admin_session"
AUTH_MAX_AGE = 60 * 60 * 12
SESSION_IDLE_TIMEOUT_SECONDS = int(os.getenv("ADMIN_SESSION_IDLE_TIMEOUT_SECONDS", "3600"))
AUTH_SECRET = os.getenv("ADMIN_AUTH_SECRET") or LINE_CHANNEL_SECRET or secrets.token_hex(32)


def now_text():
    return datetime.now().strftime("%Y/%m/%d %H:%M:%S")


def load_json(path, default):
    if not os.path.exists(path):
        return default

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, type(default)) else default
    except:
        return default


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_admin_users():
    return load_json(ADMIN_USERS_PATH, [])


def save_admin_users(users):
    save_json(ADMIN_USERS_PATH, users)


def admin_display_name(username):
    for user in load_admin_users():
        if user.get("username") == username:
            nickname = str(user.get("nickname", "")).strip()
            return nickname or username
    return username or "管理員"


def admin_role(username):
    users = load_admin_users()
    has_manager = any(str(user.get("role") or "admin").strip() != "viewer" for user in users)

    for user in load_admin_users():
        if user.get("username") == username:
            role = str(user.get("role") or "admin").strip() or "admin"
            if role == "viewer" and not has_manager:
                return "admin"
            return role
    return "admin"


def is_readonly_admin(request):
    username = current_admin(request)
    return admin_role(username) == "viewer"


def role_label(role):
    return "唯讀" if role == "viewer" else "管理者"


def sign_value(value):
    return hmac.new(
        AUTH_SECRET.encode("utf-8"),
        value.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()


def read_auth_token(token):
    if not token:
        return None

    try:
        decoded = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
        username, expires, signature = decoded.rsplit("|", 2)
    except:
        return None

    payload = f"{username}|{expires}"

    if not hmac.compare_digest(sign_value(payload), signature):
        return None

    try:
        if int(expires) < int(time.time()):
            return None
    except:
        return None

    if not any(user.get("username") == username for user in load_admin_users()):
        return None

    return username


def current_admin(request):
    return read_auth_token(request.cookies.get(AUTH_COOKIE))


def client_ip(request):
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "-"


def device_label(user_agent):
    text = str(user_agent or "")
    low = text.lower()
    if "iphone" in low:
        return "iPhone"
    if "android" in low:
        return "Android"
    if "ipad" in low:
        return "iPad"
    if "macintosh" in low or "mac os" in low:
        return "Mac"
    if "windows" in low:
        return "Windows"
    if "linux" in low:
        return "Linux"
    return "未知裝置"


def short_user_agent(value, limit=120):
    text = str(value or "").strip()
    return text[:limit] + ("..." if len(text) > limit else "")


def duration_text(start, end):
    try:
        start_dt = datetime.strptime(start, "%Y/%m/%d %H:%M:%S")
        end_dt = datetime.strptime(end, "%Y/%m/%d %H:%M:%S")
    except:
        return "-"

    seconds = max(0, int((end_dt - start_dt).total_seconds()))
    minutes = seconds // 60
    hours = minutes // 60
    minutes = minutes % 60

    if hours:
        return f"{hours} 小時 {minutes} 分"
    return f"{minutes} 分"


def parse_time(value):
    try:
        return datetime.strptime(str(value or ""), "%Y/%m/%d %H:%M:%S")
    except:
        return None


def format_time(value):
    return value.strftime("%Y/%m/%d %H:%M:%S")


def expire_stale_admin_sessions(now=None):
    now = now or datetime.now()
    sessions = load_json(ADMIN_SESSIONS_PATH, [])
    changed = False

    for item in sessions:
        if item.get("logout_at"):
            continue

        last_seen = parse_time(item.get("last_seen_at") or item.get("login_at"))
        if not last_seen:
            continue

        idle_seconds = (now - last_seen).total_seconds()
        if idle_seconds > SESSION_IDLE_TIMEOUT_SECONDS:
            logout_at = last_seen + timedelta(seconds=SESSION_IDLE_TIMEOUT_SECONDS)
            item["logout_at"] = format_time(logout_at)
            item["logout_reason"] = "逾時登出"
            item["duration"] = duration_text(item.get("login_at", ""), item.get("logout_at", ""))
            changed = True

    if changed:
        save_json(ADMIN_SESSIONS_PATH, sessions[-500:])

    return changed


def log_admin_activity(request, action, target="", detail=""):
    username = current_admin(request)
    if not username:
        return

    records = load_json(ADMIN_ACTIVITY_PATH, [])
    records.append({
        "time": now_text(),
        "admin": username,
        "display": admin_display_name(username),
        "action": action,
        "target": target,
        "detail": detail,
        "ip": client_ip(request),
    })
    save_json(ADMIN_ACTIVITY_PATH, records[-300:])


def start_admin_session(request, username):
    expire_stale_admin_sessions()
    session_id = secrets.token_urlsafe(18)
    sessions = load_json(ADMIN_SESSIONS_PATH, [])
    sessions.append({
        "id": session_id,
        "admin": username,
        "display": admin_display_name(username),
        "login_at": now_text(),
        "last_seen_at": now_text(),
        "logout_at": "",
        "duration": "",
        "ip": client_ip(request),
        "device": device_label(request.headers.get("user-agent", "")),
        "user_agent": short_user_agent(request.headers.get("user-agent", "")),
    })
    save_json(ADMIN_SESSIONS_PATH, sessions[-500:])
    return session_id


def touch_admin_session(request):
    expire_stale_admin_sessions()
    session_id = request.cookies.get(ADMIN_SESSION_COOKIE)
    if not session_id:
        return False

    sessions = load_json(ADMIN_SESSIONS_PATH, [])
    changed = False
    active = False

    for item in sessions:
        if item.get("id") == session_id and not item.get("logout_at"):
            item["last_seen_at"] = now_text()
            item["duration"] = duration_text(item.get("login_at", ""), item.get("last_seen_at", ""))
            changed = True
            active = True
            break

    if changed:
        save_json(ADMIN_SESSIONS_PATH, sessions)

    return active


def end_admin_session(request):
    expire_stale_admin_sessions()
    session_id = request.cookies.get(ADMIN_SESSION_COOKIE)
    if not session_id:
        return

    sessions = load_json(ADMIN_SESSIONS_PATH, [])
    changed = False

    for item in sessions:
        if item.get("id") == session_id and not item.get("logout_at"):
            item["logout_at"] = now_text()
            item["last_seen_at"] = item["logout_at"]
            item["duration"] = duration_text(item.get("login_at", ""), item.get("logout_at", ""))
            changed = True
            break

    if changed:
        save_json(ADMIN_SESSIONS_PATH, sessions)
