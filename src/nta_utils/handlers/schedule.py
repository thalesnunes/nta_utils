import asyncio
import logging
import re
from functools import partial

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from nta_utils.auth import is_allowed
from nta_utils.config import GCAL_CALENDAR_ID, GCAL_CREDENTIALS_PATH, GEMINI_API_KEY
from nta_utils.services.gcal import create_days_off, create_work_days
from nta_utils.services.schedule_parser import ParsedSchedule, parse_schedule_image

logger = logging.getLogger(__name__)

WAITING_PHOTO, CONFIRMING = range(2)


async def parse_schedule(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_allowed(update):
        return ConversationHandler.END

    if not GCAL_CALENDAR_ID:
        await update.message.reply_text("Google Calendar não está configurado.")
        return ConversationHandler.END

    if not GEMINI_API_KEY:
        await update.message.reply_text("Chave de API do Gemini (GEMINI_API_KEY) não está configurada.")
        return ConversationHandler.END

    if update.message and (
        update.message.photo
        or (
            update.message.document
            and (
                (update.message.document.mime_type and update.message.document.mime_type.startswith("image/"))
                or (update.message.document.file_name and update.message.document.file_name.lower().endswith((".png", ".jpg", ".jpeg", ".webp")))
            )
        )
    ):
        return await receive_photo(update, context)

    await update.message.reply_text(
        "Envie uma captura de tela da sua escala de trabalho."
    )
    return WAITING_PHOTO


async def receive_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_allowed(update):
        return ConversationHandler.END

    if not GCAL_CALENDAR_ID:
        await update.message.reply_text("Google Calendar não está configurado.")
        return ConversationHandler.END

    if not GEMINI_API_KEY:
        await update.message.reply_text("Chave de API do Gemini (GEMINI_API_KEY) não está configurada.")
        return ConversationHandler.END

    if update.message.photo:
        file_id = update.message.photo[-1].file_id
        mime_type = "image/jpeg"
    elif update.message.document and (
        (update.message.document.mime_type and update.message.document.mime_type.startswith("image/"))
        or (update.message.document.file_name and update.message.document.file_name.lower().endswith((".png", ".jpg", ".jpeg", ".webp")))
    ):
        file_id = update.message.document.file_id
        mime_type = update.message.document.mime_type or "image/jpeg"
    else:
        await update.message.reply_text("Por favor, envie uma captura de tela da sua escala.")
        return WAITING_PHOTO

    try:
        file = await context.bot.get_file(file_id, read_timeout=30, connect_timeout=30)
    except Exception as e:
        logger.warning("Timeout downloading photo, retrying: %s", e)
        file = await context.bot.get_file(file_id, read_timeout=60, connect_timeout=60)

    image_bytes = await file.download_as_bytearray()

    status_msg = await update.message.reply_text("Analisando escala...")

    try:
        loop = asyncio.get_running_loop()
        parsed: ParsedSchedule = await loop.run_in_executor(
            None,
            partial(parse_schedule_image, bytes(image_bytes), mime_type=mime_type),
        )
    except Exception as e:
        logger.error("Error parsing schedule image: %s", e, exc_info=True)
        await status_msg.edit_text(f"Erro ao analisar imagem: {e}")
        return ConversationHandler.END

    context.user_data["parsed_schedule"] = parsed

    off_str = ", ".join(str(d) for d in parsed.days_off) or "(nenhum)"
    work_str = ", ".join(str(d) for d in parsed.work_days) or "(nenhum)"

    keyboard = [
        [
            InlineKeyboardButton("Apenas folgas", callback_data="off"),
            InlineKeyboardButton("Apenas trabalho", callback_data="work"),
        ],
        [
            InlineKeyboardButton("Ambos", callback_data="both"),
            InlineKeyboardButton("Cancelar", callback_data="cancel"),
        ],
    ]

    await status_msg.edit_text(
        f"Escala analisada de *{parsed.month}*:\n\n"
        f"*Folgas:* {off_str}\n"
        f"*Trabalho:* {work_str}\n\n"
        "O que você deseja criar no Google Calendar?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return CONFIRMING


async def confirm_creation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    if query.data == "cancel":
        context.user_data.pop("parsed_schedule", None)
        await query.edit_message_text("Cancelado.")
        return ConversationHandler.END

    parsed: ParsedSchedule = context.user_data.pop("parsed_schedule", None)
    if not parsed:
        await query.edit_message_text("Nenhuma escala encontrada. Envie /escala novamente.")
        return ConversationHandler.END

    status_msg = await query.edit_message_text("Criando eventos...")

    results = []

    try:
        loop = asyncio.get_running_loop()

        if query.data in ("off", "both"):
            result = await loop.run_in_executor(
                None,
                partial(
                    create_days_off,
                    calendar_id=GCAL_CALENDAR_ID,
                    credentials_path=GCAL_CREDENTIALS_PATH,
                    days=parsed.days_off,
                    month=parsed.month,
                ),
            )
            results.append(f"Criado(s) {len(result['created'])} dia(s) de folga")

        if query.data in ("work", "both"):
            result = await loop.run_in_executor(
                None,
                partial(
                    create_work_days,
                    calendar_id=GCAL_CALENDAR_ID,
                    credentials_path=GCAL_CREDENTIALS_PATH,
                    days=parsed.work_days,
                    month=parsed.month,
                ),
            )
            results.append(f"Criado(s) {len(result['created'])} dia(s) de trabalho")

        await status_msg.edit_text(f"Pronto!\n" + "\n".join(results))

    except Exception as e:
        logger.error("Error creating events: %s", e, exc_info=True)
        await status_msg.edit_text(f"Erro: {e}")

    return ConversationHandler.END


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_allowed(update):
        context.user_data.pop("parsed_schedule", None)
        await update.message.reply_text("Cancelado.")
    return ConversationHandler.END


def get_schedule_handler() -> ConversationHandler:
    image_filter = filters.PHOTO | filters.Document.IMAGE
    caption_filter = filters.CaptionRegex(re.compile(r"^\s*/?escala(?:\s|@|$)", re.IGNORECASE))

    return ConversationHandler(
        entry_points=[
            CommandHandler("escala", parse_schedule),
            MessageHandler(image_filter & caption_filter, receive_photo),
        ],
        states={
            WAITING_PHOTO: [
                MessageHandler(image_filter, receive_photo),
            ],
            CONFIRMING: [
                CallbackQueryHandler(
                    confirm_creation, pattern="^(off|work|both|cancel)$"
                ),
            ],
        },
        fallbacks=[
            CommandHandler("cancelar", cancel),
            MessageHandler(filters.Regex(re.compile(r"^\s*/?cancelar(?:\s|@|$)", re.IGNORECASE)), cancel),
        ],
    )
