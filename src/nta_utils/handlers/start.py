from telegram import Update
from telegram.ext import ContextTypes

from nta_utils.auth import is_allowed


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        return
    await update.message.reply_text(
        "Me envie um arquivo .gpx para suavizar ou alterar a data, ou um .fit para alterar a data da sessão.\n"
        "Use /folgas seguido dos números dos dias (ex: /folgas 15 22 29) para criar eventos de folga.\n"
        "Use /escala para enviar seu print da escala e criar suas folgas e plantões automaticamente."
    )
