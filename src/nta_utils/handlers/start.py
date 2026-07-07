from telegram import Update
from telegram.ext import ContextTypes

from nta_utils.auth import is_allowed


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        return
    await update.message.reply_text(
        "Me envie um arquivo .gpx e eu vou suavizar as falhas de GPS.\n"
        "Use /folgas seguido dos números dos dias (ex: /folgas 15 22 29) para criar eventos de folga."
        "Use /escala para enviar seu print da escala e criar suas folgas e plantões automaticamente."
    )
