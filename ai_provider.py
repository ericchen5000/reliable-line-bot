import json
import os

import requests
from urllib.parse import urlparse


AI_SETTINGS_PATH = "data/ai_settings.json"
DEFAULT_SETTINGS = {
    "provider": "deepseek",
    "local_api_url": "",
    "local_model": "",
    "local_api_key": "",
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

    settings["local_api_url"] = os.getenv("LOCAL_AI_API_URL", settings["local_api_url"]).strip()
    settings["local_model"] = os.getenv("LOCAL_AI_MODEL", settings["local_model"]).strip()
    settings["local_api_key"] = os.getenv("LOCAL_AI_API_KEY", settings["local_api_key"]).strip()
    return settings


def save_ai_settings(settings):
    current = load_ai_settings()
    current.update({
        "provider": str(settings.get("provider", current["provider"]) or "deepseek").strip(),
        "local_api_url": str(settings.get("local_api_url", current["local_api_url"]) or "").strip(),
        "local_model": str(settings.get("local_model", current["local_model"]) or "").strip(),
    })

    local_api_key = str(settings.get("local_api_key", "") or "").strip()
    if local_api_key:
        current["local_api_key"] = local_api_key

    if current["provider"] not in {"deepseek", "local"}:
        current["provider"] = "deepseek"

    os.makedirs(os.path.dirname(AI_SETTINGS_PATH), exist_ok=True)
    with open(AI_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(current, f, ensure_ascii=False, indent=2)

    return current


def provider_label(provider=None):
    value = provider or load_ai_settings().get("provider", "deepseek")
    return "落地模型" if value == "local" else "DeepSeek"


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


def ask_ai(system_prompt, user_message):
    settings = load_ai_settings()

    if settings.get("provider") == "local":
        return ask_local_model(system_prompt, user_message, settings)

    return ask_deepseek_model(system_prompt, user_message)


def ask_deepseek_model(system_prompt, user_message):
    api_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
    api_url = os.getenv("DEEPSEEK_API_URL", "https://api.deepseek.com/v1/chat/completions").strip()
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip()

    if not api_key:
        raise RuntimeError("尚未設定 DEEPSEEK_API_KEY")

    return post_openai_compatible(api_url, model, api_key, system_prompt, user_message)


def ask_local_model(system_prompt, user_message, settings=None):
    settings = settings or load_ai_settings()
    api_url = settings.get("local_api_url", "").strip()
    model = settings.get("local_model", "").strip() or os.getenv("LOCAL_AI_MODEL", "local-model").strip()
    api_key = settings.get("local_api_key", "").strip()

    if not api_url:
        raise RuntimeError("尚未設定落地模型 API URL")

    return post_openai_compatible(api_url, model, api_key, system_prompt, user_message)


def post_openai_compatible(api_url, model, api_key, system_prompt, user_message):
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
    }

    response = requests.post(api_url, headers=headers, json=payload, timeout=90)
    response.raise_for_status()
    data = response.json()

    try:
        return data["choices"][0]["message"]["content"]
    except Exception as exc:
        raise RuntimeError(f"AI 回應格式無法解析：{exc}")
