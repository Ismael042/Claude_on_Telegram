import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
ALLOWED_USER_ID: int = int(os.getenv("ALLOWED_USER_ID", "0"))
CLAUDE_DEFAULT_DIR: str = os.getenv("CLAUDE_DEFAULT_DIR", ".")
