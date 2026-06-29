import os
from dotenv import load_dotenv

load_dotenv()

# LINE
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

# DeepSeek
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_API_URL = os.getenv(
    "DEEPSEEK_API_URL",
    "https://api.deepseek.com/v1/chat/completions"
)

# Files
FAQ_FILE = "data/faq.json"
SYSTEM_PROMPT_FILE = "prompts/system_prompt.txt"
WEBSITE_FILE = "website/urls.json"
KNOWLEDGE_PATH = "knowledge"
