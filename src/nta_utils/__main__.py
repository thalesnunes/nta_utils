import logging

from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
)

from nta_utils.config import TELEGRAM_BOT_TOKEN
from nta_utils.handlers.gcal import days_off
from nta_utils.handlers.gpx import handle_gpx
from nta_utils.handlers.start import start

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main() -> None:
    if not TELEGRAM_BOT_TOKEN:
        raise RuntimeError("TELEGRAM_BOT_TOKEN environment variable is not set")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("days_off", days_off))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_gpx))

    logger.info("Bot started")
    app.run_polling()


if __name__ == "__main__":
    main()
