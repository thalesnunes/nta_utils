import json
import logging
from datetime import date, timedelta
from pathlib import Path

from google.oauth2.service_account import Credentials
from gcsa.event import Event
from gcsa.google_calendar import GoogleCalendar

from nta_utils.config import (
    GCAL_DAY_OFF_COLOR,
    GCAL_DAY_OFF_TITLE,
    GCAL_WORK_DAY_COLOR,
    GCAL_WORK_DAY_TITLE,
)

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Google Calendar Event Colors (from GoogleCalendar().list_event_colors())
EVENT_COLORS: dict[str, str] = {
    "lavender": "1",
    "sage": "2",
    "grape": "3",
    "flamingo": "4",
    "banana": "5",
    "tangerine": "6",
    "peacock": "7",
    "graphite": "8",
    "blueberry": "9",
    "basil": "10",
    "tomato": "11",
}

EVENT_COLOR_ALIASES: dict[str, str] = {
    # Portuguese aliases
    "lavanda": "1",
    "salvia": "2",
    "sálvia": "2",
    "uva": "3",
    "tangerina": "6",
    "pavao": "7",
    "pavão": "7",
    "grafite": "8",
    "mirtilo": "9",
    "manjericao": "10",
    "manjericão": "10",
    "tomate": "11",
    # Hex codes returned by list_event_colors()
    "#a4bdfc": "1",
    "#7ae7bf": "2",
    "#dbadff": "3",
    "#ff887c": "4",
    "#fbd75b": "5",
    "#ffb878": "6",
    "#46d6db": "7",
    "#e1e1e1": "8",
    "#5484ed": "9",
    "#51b749": "10",
    "#dc2127": "11",
}


def resolve_color_id(color: str | None) -> str | None:
    """Resolve a color name, alias, hex code, or ID to a Google Calendar event color_id."""
    if not color:
        return None
    cleaned = color.strip().lower()
    if cleaned in EVENT_COLORS:
        return EVENT_COLORS[cleaned]
    if cleaned in EVENT_COLOR_ALIASES:
        return EVENT_COLOR_ALIASES[cleaned]
    if cleaned in {str(i) for i in range(1, 12)}:
        return cleaned
    logger.warning(
        "Unknown Google Calendar event color: '%s'. Event will use calendar default.",
        color,
    )
    return None


def _load_credentials(credentials_path: Path):
    with open(credentials_path) as f:
        data = json.load(f)
    if data.get("type") == "service_account":
        return Credentials.from_service_account_file(
            str(credentials_path), scopes=SCOPES
        )
    return None


def _get_calendar(calendar_id: str, credentials_path: Path) -> GoogleCalendar:
    if not credentials_path.exists():
        raise FileNotFoundError(
            f"Google Calendar credentials not found at {credentials_path}"
        )

    credentials = _load_credentials(credentials_path)
    if credentials:
        return GoogleCalendar(calendar_id, credentials=credentials)
    return GoogleCalendar(calendar_id, credentials_path=str(credentials_path))


def _resolve_target_month(month: str | None = None) -> date:
    if month:
        return date.fromisoformat(month + "-01")
    target_date = date.today()
    if target_date.day >= 20:
        target_date += timedelta(days=12)
    return target_date.replace(day=1)


def _create_events(
    calendar_id: str,
    credentials_path: Path,
    days: list[int],
    title: str,
    month: str | None = None,
    color_id: str | None = None,
) -> dict:
    calendar = _get_calendar(calendar_id, credentials_path)
    target_date = _resolve_target_month(month)

    created: list[str] = []
    for day in days:
        event_date = target_date.replace(day=day)
        event = Event(
            title,
            start=event_date,
            end=event_date,
            transparency="transparent",
            color_id=color_id,
        )
        calendar.add_event(event)
        created.append(event_date.isoformat())

    return {"created": created, "month": target_date.strftime("%Y-%m")}


def create_days_off(
    calendar_id: str,
    credentials_path: Path,
    days: list[int],
    month: str | None = None,
    title: str | None = None,
    color: str | None = None,
) -> dict:
    event_title = title if title is not None else GCAL_DAY_OFF_TITLE
    event_color = color if color is not None else GCAL_DAY_OFF_COLOR
    return _create_events(
        calendar_id,
        credentials_path,
        days,
        event_title,
        month,
        resolve_color_id(event_color),
    )


def create_work_days(
    calendar_id: str,
    credentials_path: Path,
    days: list[int],
    month: str | None = None,
    title: str | None = None,
    color: str | None = None,
) -> dict:
    event_title = title if title is not None else GCAL_WORK_DAY_TITLE
    event_color = color if color is not None else GCAL_WORK_DAY_COLOR
    return _create_events(
        calendar_id,
        credentials_path,
        days,
        event_title,
        month,
        resolve_color_id(event_color),
    )


def list_event_colors(calendar_id: str, credentials_path: Path) -> dict:
    calendar = _get_calendar(calendar_id, credentials_path)
    return calendar.list_event_colors()
