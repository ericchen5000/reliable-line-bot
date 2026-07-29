import json
import os
import time

import requests
from urllib.parse import urlparse


AI_SETTINGS_PATH = "data/ai_settings.json"
DEFAULT_LOCAL_API_URL = "http://127.0.0.1:11434/v1/chat/completions"
DEFAULT_SETTINGS = {
    "provider": "deepseek",
    "strategy": "fixed",
    "local_api_url": "",
    "local_model": "",
    "local_api_key": "",
    "reply_char_limit": "600",
    "kb_cleanup_mode": "ai_light",
}


def load_ai_settings():
    settings = DEFAULT_SETTINGS.copy()

    if os.path.exists(AI_SETTINGS_PATH):
        try:
            with open(AI_SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    settings.update({
                        key: str(data.get(key, settings[key]) or "").strip()
                        for key in settings
                    })
        except:
            pass

    if settings["provider"] not in {"deepseek", "local"}:
        settings["provider"] = "deepseek"

    if settings["strategy"] not in {"fixed", "smart"}:
        settings["strategy"] = "fixed"

    settings["local_api_url"] = os.getenv("LOCAL_AI_API_URL", settings["local_api_url"]).strip()
    settings["local_model"] = os.getenv("LOCAL_AI_MODEL", settings["local_model"]).strip()
    settings["local_api_key"] = os.getenv("LOCAL_AI_API_KEY", settings["local_api_key"]).strip()
    return settings


def save_ai_settings(settings):
    current = load_ai_settings()
    provider = str(settings.get("provider", current["provider"]) or "deepseek").strip()
    strategy = str(settings.get("strategy", current["strategy"]) or "fixed").strip()
    local_api_url = str(settings.get("local_api_url", current["local_api_url"]) or "").strip()
    local_model = str(settings.get("local_model", current["local_model"]) or "").strip()
    reply_char_limit = str(settings.get("reply_char_limit", current["reply_char_limit"]) or "600").strip()
    kb_cleanup_mode = str(settings.get("kb_cleanup_mode", current["kb_cleanup_mode"]) or "ai_light").strip()

    if (provider == "local" or strategy == "smart") and local_model and not local_api_url:
        local_api_url = DEFAULT_LOCAL_API_URL

    current.update({
        "provider": provider,
        "strategy": strategy,
        "local_api_url": local_api_url,
        "local_model": local_model,
        "reply_char_limit": normalize_reply_char_limit(reply_char_limit),
        "kb_cleanup_mode": kb_cleanup_mode if kb_cleanup_mode in {"basic", "ai_light"} else "ai_light",
    })

    local_api_key = str(settings.get("local_api_key", "") or "").strip()
    if local_api_key:
        current["local_api_key"] = local_api_key

    if current["provider"] not in {"deepseek", "local"}:
        current["provider"] = "deepseek"

    if current["strategy"] not in {"fixed", "smart"}:
        current["strategy"] = "fixed"

    os.makedirs(os.path.dirname(AI_SETTINGS_PATH), exist_ok=True)
    with open(AI_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)

    return current


def normalize_reply_char_limit(value):
    try:
        limit = int(str(value or "").strip())
    except:
        limit = 600
    return str(max(150, min(2000, limit)))


def reply_char_limit(settings=None):
    settings = settings or load_ai_settings()
    return int(normalize_reply_char_limit(settings.get("reply_char_limit", "600")))


def answer_max_tokens(settings=None):
    limit = reply_char_limit(settings)
    return max(300, min(2600, int(limit * 1.8)))


def apply_reply_length_rule(system_prompt, settings=None):
    limit = reply_char_limit(settings)
    return (
        f"{system_prompt}\n\n"
        "回答長度規則：\n"
        f"- 請將正式回答控制在約 {limit} 個中文字以內。\n"
        "- 請在字數範圍內完整回答，不要因為長度限制而在句子中途斷掉。\n"
        "- 優先回答使用者真正問的重點；若內容很多，請摘要重點，不要展開過多細節。\n"
        "- 不要提到你受到字數限制。"
    )


def provider_label(provider=None):
    value = provider or load_ai_settings().get("provider", "deepseek")
    return "本地模型" if value == "local" else "DeepSeek"


def current_ai_identity():
    settings = load_ai_settings()
    provider = settings.get("provider", "deepseek")
    if settings.get("strategy") == "smart":
        cloud_model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip()
        local_model = settings.get("local_model", "").strip() or os.getenv("LOCAL_AI_MODEL", "-").strip()
        return {
            "provider": "smart",
            "provider_label": "智慧混合",
            "model": f"本地模型 {local_model or '-'} + DeepSeek {cloud_model}",
            "strategy": "smart",
            "strategy_label": "智慧混合",
        }

    if provider == "local":
        model = settings.get("local_model", "").strip() or os.getenv("LOCAL_AI_MODEL", "local-model").strip()
    else:
        model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip()

    return {
        "provider": provider,
        "provider_label": provider_label(provider),
        "model": model or "-",
        "strategy": settings.get("strategy", "fixed"),
        "strategy_label": "智慧混合" if settings.get("strategy") == "smart" else "固定模型",
    }


def local_model_base_urls(api_url=""):
    urls = []
    candidates = [str(api_url or "").strip(), "http://127.0.0.1:11434/v1/chat/completions"]

    for candidate in candidates:
        if not candidate:
            continue

        parsed = urlparse(candidate)
        if not parsed.scheme or not parsed.netloc:
            continue

        root = f"{parsed.scheme}://{parsed.netloc}"
        path = parsed.path.rstrip("/")

        if path.endswith("/v1/chat/completions"):
            urls.append((root, root + "/api/tags", root + "/v1/models"))
        elif path.endswith("/api/chat"):
            urls.append((root, root + "/api/tags", root + "/v1/models"))
        else:
            urls.append((root, root + "/api/tags", root.rstrip("/") + "/v1/models"))

    result = []
    seen = set()
    for item in urls:
        if item[0] not in seen:
            seen.add(item[0])
            result.append(item)
    return result


def list_local_models(api_url=""):
    errors = []

    for _, ollama_tags_url, openai_models_url in local_model_base_urls(api_url):
        try:
            response = requests.get(ollama_tags_url, timeout=3)
            if response.ok:
                data = response.json()
                models = data.get("models", [])
                names = [
                    str(item.get("name", "")).strip()
                    for item in models
                    if isinstance(item, dict) and item.get("name")
                ]
                if names:
                    return {
                        "ok": True,
                        "source": "Ollama",
                        "models": names,
                        "message": f"已抓到 {len(names)} 個 Ollama 模型",
                    }
        except Exception as exc:
            errors.append(str(exc))

        try:
            response = requests.get(openai_models_url, timeout=3)
            if response.ok:
                data = response.json()
                models = data.get("data", [])
                names = [
                    str(item.get("id", "")).strip()
                    for item in models
                    if isinstance(item, dict) and item.get("id")
                ]
                if names:
                    return {
                        "ok": True,
                        "source": "OpenAI 相容模型清單",
                        "models": names,
                        "message": f"已抓到 {len(names)} 個模型",
                    }
        except Exception as exc:
            errors.append(str(exc))

    return {
        "ok": False,
        "source": "-",
        "models": [],
        "message": "目前抓不到模型清單，可手動輸入模型名稱。",
        "errors": errors[-2:],
    }


def ask_ai(system_prompt, user_message, task="general"):
    settings = load_ai_settings()
    if task == "kb_cleanup":
        max_tokens = 2600
    else:
        system_prompt = apply_reply_length_rule(system_prompt, settings)
        max_tokens = answer_max_tokens(settings)

    if settings.get("strategy") == "smart":
        if task in {"site_index", "website", "summary"}:
            return ask_local_with_cloud_fallback(system_prompt, user_message, settings, max_tokens=max_tokens)
        return ask_deepseek_model(system_prompt, user_message, settings=settings, max_tokens=max_tokens)

    if settings.get("provider") == "local":
        return ask_local_with_cloud_fallback(system_prompt, user_message, settings, max_tokens=max_tokens)

    return ask_deepseek_model(system_prompt, user_message, settings=settings, max_tokens=max_tokens)


def ask_local_with_cloud_fallback(system_prompt, user_message, settings=None, max_tokens=None):
    settings = settings or load_ai_settings()
    max_tokens = max_tokens or answer_max_tokens(settings)

    if not settings.get("local_model", "").strip() and not os.getenv("LOCAL_AI_MODEL", "").strip():
        return ask_deepseek_model(system_prompt, user_message, settings=settings, max_tokens=max_tokens)

    try:
        return ask_local_model(system_prompt, user_message, settings, max_tokens=max_tokens)
    except Exception:
        time.sleep(1)
        try:
            return ask_local_model(system_prompt, user_message, settings, max_tokens=max_tokens)
        except Exception as local_exc:
            if os.getenv("DEEPSEEK_API_KEY", "").strip():
                try:
                    return ask_deepseek_model(system_prompt, user_message, settings=settings, max_tokens=max_tokens)
                except Exception as cloud_exc:
                    return (
                        "目前 AI 模型暫時無法回應，請稍後再試。"
                        f"\n\n本地模型錯誤：{friendly_ai_error(local_exc)}"
                        f"\nDeepSeek 備援錯誤：{friendly_ai_error(cloud_exc)}"
                    )

            return (
                "目前本地模型暫時無法回應，請稍後再試，或請管理者確認 Ollama 是否啟動、"
                "模型是否已下載、VPS 記憶體是否足夠。"
                f"\n\n錯誤摘要：{friendly_ai_error(local_exc)}"
            )


def ask_deepseek_model(system_prompt, user_message, settings=None, max_tokens=None):
    settings = settings or load_ai_settings()
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    api_url = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions").strip()
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip()

    if not api_key:
        raise RuntimeError("尚未設定 DEEPSEEK_API_KEY")

    return post_openai_compatible(api_url, model, api_key, system_prompt, user_message, max_tokens=max_tokens or answer_max_tokens(settings))


def ask_local_model(system_prompt, user_message, settings=None, max_tokens=None):
    settings = settings or load_ai_settings()
    api_url = settings.get("local_api_url", "").strip() or DEFAULT_LOCAL_API_URL
    model = settings.get("local_model", "").strip() or os.getenv("LOCAL_AI_MODEL", "local-model").strip()
    api_key = settings.get("local_api_key", "").strip()

    if not api_url:
        raise RuntimeError("尚未設定本地模型 API URL")

    return post_openai_compatible(api_url, model, api_key, system_prompt, user_message, timeout=180, max_tokens=max_tokens or answer_max_tokens(settings))


def friendly_ai_error(exc):
    text = str(exc)
    if "RemoteDisconnected" in text or "Connection aborted" in text:
        return "本地模型服務中途關閉連線，可能是模型載入失敗、記憶體不足或 Ollama 服務尚未準備好。"
    if "Connection refused" in text or "Failed to establish" in text:
        return "無法連線到模型服務，請確認 Ollama 是否正在執行。"
    if "Read timed out" in text or "timed out" in text:
        return "模型回應逾時，可能是模型太大或 VPS 資源不足。"
    return text[:300]


def post_openai_compatible(api_url, model, api_key, system_prompt, user_message, timeout=90, max_tokens=700):
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": 0.3,
        "max_tokens": max_tokens,
    }

    response = requests.post(api_url, headers=headers, json=payload, timeout=timeout)
    response.raise_for_status()
    data = response.json()

    try:
        return data["choices"][0]["message"]["content"]
    except Exception as exc:
        raise RuntimeError(f"AI 回應格式無法解析：{exc}")
