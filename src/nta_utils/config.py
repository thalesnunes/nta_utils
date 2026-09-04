import os
from pathlib import Path


TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_ALLOWED_USERS: set[int] = set()

_raw_users = os.environ.get("TELEGRAM_ALLOWED_USERS", "")
if _raw_users:
    TELEGRAM_ALLOWED_USERS = {
        int(uid.strip()) for uid in _raw_users.split(",") if uid.strip()
    }

GCAL_CALENDAR_ID: str = os.environ.get("GCAL_CALENDAR_ID", "")
GCAL_CREDENTIALS_PATH: Path = Path(
    os.environ.get("GCAL_CREDENTIALS_PATH", "/app/credentials/credentials.json")
)
GCAL_DAY_OFF_TITLE: str = os.environ.get("GCAL_DAY_OFF_TITLE", "Folga")
GCAL_DAY_OFF_COLOR: str = os.environ.get("GCAL_DAY_OFF_COLOR", "flamingo")
GCAL_WORK_DAY_TITLE: str = os.environ.get("GCAL_WORK_DAY_TITLE", "Noite")
GCAL_WORK_DAY_COLOR: str = os.environ.get("GCAL_WORK_DAY_COLOR", "peacock")

GEMINI_API_KEY: str = os.environ.get("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
