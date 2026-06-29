import os
from core.db import log_chat
from core.knowledge import search_knowledge
from core.faq_runtime import match_faq
from deepseek import ask_deepseek


# --------------------------------------------------
# load system prompt（如果有設定）
# --------------------------------------------------
SYSTEM_PROMPT_FILE = "data/system_prompt.txt"


def load_prompt():
    if os.path.exists(SYSTEM_PROMPT_FILE):
        with open(SYSTEM_PROMPT_FILE, "r", encoding="utf-8") as f:
            return f.read()
    return ""


SYSTEM_PROMPT = load_prompt()


# --------------------------------------------------
# AI CORE
# --------------------------------------------------
def ai_reply(user_message: str):

    msg = user_message.lower()

    # --------------------------------------------------
    # 1️⃣ FAQ 優先（最高優先級）
    # --------------------------------------------------
    faq_answer = match_faq(msg)
    if faq_answer:
        log_chat("line", user_message, faq_answer)
        return faq_answer

    # --------------------------------------------------
    # 2️⃣ Knowledge Base（文件搜尋）
    # --------------------------------------------------
    knowledge = search_knowledge(msg)
    if knowledge:
        log_chat("line", user_message, knowledge)
        return knowledge

    # --------------------------------------------------
    # 3️⃣ LLM fallback（DeepSeek）
    # --------------------------------------------------
    prompt = SYSTEM_PROMPT + """

規則：
1. 不可亂編資料
2. 不知道就說「資料庫中沒有相關資訊」
3. 使用繁體中文回答
4. 回答要簡短清楚
"""

    reply = ask_deepseek(prompt, user_message)

    # log
    log_chat("line", user_message, reply)

    return reply
