# AGENTS.md - nta_utils

## Project Overview

Telegram bot for utility commands: GPX smoothing and Google Calendar day-off management. Written in Python 3.12 using `uv` for package management.

## Commands

- `/start` - Welcome message and usage instructions
- `/folgas <days...>` - Create "Folga" events on Google Calendar for specified days
- `/escala` - Send a schedule screenshot to auto-create work/off events
- `/cancelar` - Cancel current conversation
- Any `.gpx` file - Smoothed GPX file returned

## Project Structure

```
src/nta_utils/
├── __main__.py              # Entry point, registers handlers
├── config.py                # Environment variables (TELEGRAM_BOT_TOKEN, GCAL_*)
├── auth.py                  # User whitelist check
├── handlers/
│   ├── start.py             # /start command
│   ├── gpx.py               # GPX file upload handler
│   ├── gcal.py              # /folgas command
│   └── schedule.py          # /escala conversation (OCR → calendar)
└── services/
    ├── gpx_transformer.py   # GPX interpolation logic
    ├── gcal.py              # Google Calendar API wrapper
    └── schedule_parser.py   # OCR schedule image parsing
```

## Environment Variables

- `TELEGRAM_BOT_TOKEN` - Required. Telegram bot token from @BotFather
- `TELEGRAM_ALLOWED_USERS` - Optional. Comma-separated Telegram user IDs for access control
- `GCAL_CALENDAR_ID` - Required for calendar features. Google Calendar ID
- `GCAL_CREDENTIALS_PATH` - Optional. Path to Google credentials JSON (default: `/app/credentials/credentials.json`)

## Development

### Running locally

```bash
uv sync
uv run python -m nta_utils
```

### Running with Docker

```bash
docker compose up -d
```

## Dependencies

- `python-telegram-bot>=21.0` - Telegram Bot API
- `gcsa>=2.0` - Google Calendar Simple API
- `gpx>=2026.3.0` - GPX file handling
- `Pillow>=10.0` - Image processing
- `pytesseract>=0.3.10` - OCR for schedule parsing

## Conventions

- All user-facing messages in Portuguese (Brazilian)
- Async handlers using `python-telegram-bot` patterns
- Services are synchronous; handlers use `run_in_executor` for blocking calls
- Logging via standard library `logging` module
- Auth checks at the start of every handler via `is_allowed()`
- Google Calendar operations use service account credentials

---

## Maintenance Rule

**AGENTS.md and README.md must be updated after EVERY feature update or major restructure.**

When making changes that affect:
- Module structure (new files, renamed files, moved directories)
- Configuration options (new env vars, changed defaults)
- Architecture decisions (new services, changed dependencies)

Update this file immediately in the same PR/branch. The documentation is a first-class artifact — keeping it current prevents knowledge drift and onboarding friction.
