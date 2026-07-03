# nta_utils

Telegram bot with utility commands: GPX smoothing and Google Calendar day-off management.

## Features

- **GPX Smoothing** — Send a `.gpx` file from Samsung Health and get back a smoothed version with GPS gaps interpolated at 1-second intervals (so Strava shows accurate elapsed time).
- **Days Off** — Use `/days_off 15 22 29` to create "Folga Nati" events on a shared Google Calendar.

## Setup

### 1. Create a Telegram bot

1. Open Telegram and message [@BotFather](https://t.me/BotFather)
2. Send `/newbot` and follow the prompts
3. Copy the bot token you receive

### 2. Configure

```bash
cp .env.example .env
# Edit .env and paste your bot token
```

### 3. Google Calendar (optional)

If you want the `/days_off` command:

1. Create or select a Google Cloud project
2. Enable the Google Calendar API
3. Create a Service Account or OAuth credentials
4. Download the credentials JSON and place it at `./credentials.json` (repo root)
5. Set `GCAL_CALENDAR_ID` in `.env` to your target calendar ID

### 4. Run with Docker Compose

```bash
docker compose up -d
```

### Or run locally

```bash
uv sync
uv run python -m bot
```

## Usage

1. Open your bot in Telegram
2. Send `/start` for a welcome message
3. **GPX**: Send any `.gpx` file — receive the smoothed file back
4. **Days Off**: Send `/days_off 15 22 29` — events are created on the configured calendar

## Project structure

```
src/bot/
├── __main__.py          # Entry point
├── config.py            # Environment variable loading
├── auth.py              # User whitelist
├── handlers/
│   ├── start.py         # /start command
│   ├── gpx.py           # GPX file handler
│   └── gcal.py          # /days_off command
└── services/
    ├── gpx_transformer.py  # GPX interpolation logic
    └── gcal.py             # Google Calendar integration
```

## Security

- `.env` and credential files are gitignored — never committed
- Calendar ID and credentials path are configured via environment variables
- Optional user whitelist (`TELEGRAM_ALLOWED_USERS`) restricts bot access
