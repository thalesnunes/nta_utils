import logging
import os
import tempfile
from pathlib import Path

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from gpx_transformer import fill_gaps

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

ALLOWED_USERS: set[int] = set()
raw = os.environ.get("TELEGRAM_ALLOWED_USERS", "")
if raw:
    ALLOWED_USERS = {int(uid.strip()) for uid in raw.split(",") if uid.strip()}


def is_allowed(update: Update) -> bool:
    if not ALLOWED_USERS:
        return True
    user_id = update.effective_user.id if update.effective_user else None
    return user_id in ALLOWED_USERS if user_id else False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        return
    await update.message.reply_text(
        "Send me a .gpx file and I'll smooth out GPS gaps."
    )


async def handle_gpx(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        return
    document = update.message.document
    if not document or not document.file_name.endswith(".gpx"):
        await update.message.reply_text("Please send a .gpx file.")
        return

    status_msg = await update.message.reply_text("Processing...")

    try:
        file = await document.get_file()
        with tempfile.TemporaryDirectory() as tmp:
            input_path = Path(tmp) / document.file_name
            output_path = Path(tmp) / f"smoothed_{document.file_name}"
            await file.download_to_drive(input_path)

            result = fill_gaps(str(input_path), str(output_path))

            with open(output_path, "rb") as f:
                await update.message.reply_document(
                    document=f,
                    filename=f"smoothed_{document.file_name}",
                )
            await status_msg.edit_text(
                f"Done! Added {result['interpolated']} interpolated points."
            )
    except Exception as e:
        logger.error("Error processing GPX: %s", e, exc_info=True)
        await status_msg.edit_text(f"Error: {e}")


def main() -> None:
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is not set")

    app = ApplicationBuilder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_gpx))
    app.run_polling()


if __name__ == "__main__":
    main()
