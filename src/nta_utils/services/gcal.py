import json
from datetime import date, timedelta
from pathlib import Path

from google.oauth2.service_account import Credentials
from gcsa.event import Event
from gcsa.google_calendar import GoogleCalendar

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def _load_credentials(credentials_path: Path):
    with open(credentials_path) as f:
        data = json.load(f)
    if data.get("type") == "service_account":
        return Credentials.from_service_account_file(
            str(credentials_path), scopes=SCOPES
        )
    return None


def create_days_off(
    calendar_id: str,
    credentials_path: Path,
    days: list[int],
) -> dict:
    if not credentials_path.exists():
        raise FileNotFoundError(
            f"Google Calendar credentials not found at {credentials_path}"
        )

    credentials = _load_credentials(credentials_path)
    if credentials:
        calendar = GoogleCalendar(calendar_id, credentials=credentials)
    else:
        calendar = GoogleCalendar(calendar_id, credentials_path=str(credentials_path))

    target_date = date.today()
    if target_date.day >= 20:
        target_date += timedelta(days=12)

    created: list[str] = []
    for day in days:
        event_date = target_date.replace(day=day)
        event = Event(
            "Folga Nati",
            start=event_date,
            end=event_date,
            transparency="transparent",
        )
        calendar.add_event(event)
        created.append(event_date.isoformat())

    return {"created": created, "month": target_date.strftime("%Y-%m")}
