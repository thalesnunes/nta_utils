import asyncio
import logging
from functools import partial

from telegram import Update
from telegram.ext import ContextTypes

from nta_utils.auth import is_allowed
from nta_utils.config import GCAL_CALENDAR_ID, GCAL_CREDENTIALS_PATH
from nta_utils.services.gcal import create_days_off

logger = logging.getLogger(__name__)


async def days_off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        return

    if not GCAL_CALENDAR_ID:
        await update.message.reply_text("Google Calendar is not configured.")
        return

    raw_args = context.args
    if not raw_args:
        await update.message.reply_text(
            "Usage: /days_off 15 22 29\n"
            "Provide one or more day-of-month numbers."
        )
        return

    try:
        days = [int(arg) for arg in raw_args]
    except ValueError:
        await update.message.reply_text("All arguments must be numbers (day of month).")
        return

    invalid = [d for d in days if d < 1 or d > 31]
    if invalid:
        await update.message.reply_text(
            f"Invalid day(s): {', '.join(str(d) for d in invalid)}. Must be 1-31."
        )
        return

    status_msg = await update.message.reply_text("Creating day-off events...")

    try:
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            None,
            partial(
                create_days_off,
                calendar_id=GCAL_CALENDAR_ID,
                credentials_path=GCAL_CREDENTIALS_PATH,
                days=days,
            ),
        )
        await status_msg.edit_text(
            f"Created {len(result['created'])} day(s) off in {result['month']}:\n"
            + "\n".join(f"  - {d}" for d in result["created"])
        )
    except FileNotFoundError as e:
        logger.error("Google Calendar credentials not found: %s", e)
        await status_msg.edit_text(f"Credentials error: {e}")
    except Exception as e:
        logger.error("Error creating day-off events: %s", e, exc_info=True)
        await status_msg.edit_text(f"Error: {e}")
