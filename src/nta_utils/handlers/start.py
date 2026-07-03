from telegram import Update
from telegram.ext import ContextTypes

from nta_utils.auth import is_allowed


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        return
    await update.message.reply_text(
        "Send me a .gpx file and I'll smooth out GPS gaps.\n"
        "Use /days_off followed by day numbers (e.g. /days_off 15 22 29) to create day-off events."
    )
