# nta_utils

Telegram bot with utility commands: GPX smoothing and Google Calendar day-off management.

## Features

- **GPX Smoothing & Date Modification** — Send a `.gpx` file to interpolate GPS gaps or change the workout date.
- **Days Off** — Use `/folgas 15 22 29` to create "Folga" events on a shared Google Calendar.
- **Schedule AI Analysis** — Use `/escala` to send a schedule screenshot; Gemini analyzes the image with structured outputs to detect work days and days off, then creates calendar events.

## Setup

### 1. Create a Telegram bot

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Copy the bot token you receive

### 2. Configure

Set the environment variables in your `.env` file:

```env
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_ALLOWED_USERS=123456789

# Google Calendar
GCAL_CALENDAR_ID=your_calendar_id@group.calendar.google.com
GCAL_CREDENTIALS_PATH=/app/credentials/credentials.json

# Gemini AI (AI Studio)
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-3.6-flash
```

### 3. Google Calendar (optional)

If you want calendar features (`/folgas` and `/escala`):

1. Create or select a Google Cloud project
2. Enable the Google Calendar API
3. Create a Service Account or OAuth credentials
4. Download the credentials JSON and place it at `./app/credentials/credentials.json`
5. Set `GCAL_CALENDAR_ID` in `.env` to your target calendar ID

### 4. Run with Docker Compose

```bash
docker compose up -d
```

### Or run locally

```bash
uv sync
uv run python -m nta_utils
```

## Usage

1. Open your bot in Telegram
2. Send `/start` for a welcome message
3. **GPX**: Send any `.gpx` file — choose to smooth, change date, or both
4. **Days Off**: Send `/folgas 15 22 29` — creates day-off events
5. **Schedule**: Send `/escala` and upload a schedule screenshot — Gemini extracts work days and days off

## Project structure

```
src/nta_utils/
├── __main__.py              # Entry point
├── config.py                # Environment variable loading
├── auth.py                  # User whitelist check
├── handlers/
│   ├── start.py             # /start command
│   ├── gpx.py               # GPX file handler
│   ├── gcal.py              # /folgas command
│   └── schedule.py          # /escala conversation (Gemini → calendar)
└── services/
    ├── gpx_transformer.py   # GPX interpolation logic
    ├── gcal.py              # Google Calendar integration
    └── schedule_parser.py   # Gemini structured output schedule parser
```

## Security

- `.env` and credential files are gitignored — never committed
- Calendar ID and credentials path are configured via environment variables
- Optional user whitelist (`TELEGRAM_ALLOWED_USERS`) restricts bot access
