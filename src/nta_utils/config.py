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
