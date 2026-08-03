import logging
import re
import tempfile
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    CallbackQueryHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from nta_utils.auth import is_allowed
from nta_utils.services.gpx_transformer import fill_gaps

logger = logging.getLogger(__name__)

SELECTING_ACTION, WAITING_DATE = range(2)


def _extract_date_from_filename(filename: str) -> str | None:
    """Extract date string like '20260719' from filename like '20260719_071522.gpx' or '@20260719_071522.gpx'."""
    match = re.search(r"@?(\d{8})_\d{6}\.gpx$", filename)
    if match:
        return match.group(1)
    return None


def _format_date(raw: str) -> str:
    """Convert '20260719' to '2026-07-19'."""
    return f"{raw[:4]}-{raw[4:6]}-{raw[6:8]}"


def _replace_date_in_content(content: str, old_date_compact: str, new_date_compact: str) -> str:
    """Replace all date occurrences in GPX content."""
    old_dashed = _format_date(old_date_compact)
    new_dashed = _format_date(new_date_compact)
    content = content.replace(old_dashed, new_dashed)
    content = content.replace(old_date_compact, new_date_compact)
    return content


def _new_filename(original: str, old_date_compact: str, new_date_compact: str) -> str:
    """Replace date in filename."""
    return original.replace(old_date_compact, new_date_compact)


async def receive_gpx(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_allowed(update):
        return ConversationHandler.END

    document = update.message.document
    if not document or not document.file_name.endswith(".gpx"):
        await update.message.reply_text("Por favor, envie um arquivo .gpx.")
        return ConversationHandler.END

    file = await document.get_file()
    tmp_dir = tempfile.mkdtemp()
    input_path = Path(tmp_dir) / document.file_name
    await file.download_to_drive(input_path)

    context.user_data["gpx_input_path"] = str(input_path)
    context.user_data["gpx_tmp_dir"] = tmp_dir
    context.user_data["gpx_filename"] = document.file_name

    keyboard = [
        [
            InlineKeyboardButton("Suavizar GPX", callback_data="smooth"),
        ],
        [
            InlineKeyboardButton("Alterar data da sessão", callback_data="change_date"),
        ],
        [
            InlineKeyboardButton("Suavizar + Alterar data", callback_data="both"),
        ],
    ]

    await update.message.reply_text(
        f"Arquivo recebido: `{document.file_name}`\n\nO que deseja fazer?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )
    return SELECTING_ACTION


async def handle_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    action = query.data
    context.user_data["gpx_action"] = action

    if action == "smooth":
        return await _do_smooth(query, context)
    elif action == "change_date":
        await query.edit_message_text("Envie a nova data no formato YYYY-MM-DD (ex: 2026-08-01)")
        return WAITING_DATE
    elif action == "both":
        await query.edit_message_text("Envie a nova data no formato YYYY-MM-DD (ex: 2026-08-01)")
        return WAITING_DATE

    return ConversationHandler.END


async def receive_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_allowed(update):
        return ConversationHandler.END

    text = update.message.text.strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        await update.message.reply_text("Formato inválido. Envie a data no formato YYYY-MM-DD (ex: 2026-08-01)")
        return WAITING_DATE

    new_date_compact = text.replace("-", "")
    context.user_data["gpx_new_date"] = new_date_compact

    status_msg = await update.message.reply_text("Processando...")

    try:
        input_path = Path(context.user_data["gpx_input_path"])
        filename = context.user_data["gpx_filename"]
        old_date_compact = _extract_date_from_filename(filename)

        if not old_date_compact:
            await status_msg.edit_text("Não foi possível extrair a data do nome do arquivo.")
            return ConversationHandler.END

        content = input_path.read_text(encoding="utf-8")
        new_content = _replace_date_in_content(content, old_date_compact, new_date_compact)
        input_path.write_text(new_content, encoding="utf-8")

        new_name = _new_filename(filename, old_date_compact, new_date_compact)

        if context.user_data["gpx_action"] == "both":
            output_path = input_path.parent / f"smoothed_{new_name}"
            result = fill_gaps(str(input_path), str(output_path))
            with open(output_path, "rb") as f:
                await update.message.reply_document(
                    document=f,
                    filename=f"smoothed_{new_name}",
                )
            await status_msg.edit_text(
                f"Data alterada para {_format_date(new_date_compact)} e "
                f"{result['interpolated']} pontos interpolados."
            )
        else:
            with open(input_path, "rb") as f:
                await update.message.reply_document(
                    document=f,
                    filename=new_name,
                )
            await status_msg.edit_text(
                f"Data alterada de {_format_date(old_date_compact)} para {_format_date(new_date_compact)}."
            )

    except Exception as e:
        logger.error("Error processing GPX: %s", e, exc_info=True)
        await status_msg.edit_text(f"Erro: {e}")

    _cleanup(context)
    return ConversationHandler.END


async def _do_smooth(query, context) -> int:
    status_msg = await query.edit_message_text("Suavizando GPX...")

    try:
        input_path = Path(context.user_data["gpx_input_path"])
        filename = context.user_data["gpx_filename"]
        output_path = input_path.parent / f"smoothed_{filename}"

        result = fill_gaps(str(input_path), str(output_path))

        with open(output_path, "rb") as f:
            await context.bot.send_document(
                chat_id=query.message.chat.id,
                document=f,
                filename=f"smoothed_{filename}",
            )
        await status_msg.edit_text(
            f"Pronto! Adicionado(s) {result['interpolated']} pontos interpolados."
        )

    except Exception as e:
        logger.error("Error processing GPX: %s", e, exc_info=True)
        await status_msg.edit_text(f"Erro: {e}")

    _cleanup(context)
    return ConversationHandler.END


def _cleanup(context: ContextTypes.DEFAULT_TYPE) -> None:
    import shutil

    tmp_dir = context.user_data.pop("gpx_tmp_dir", None)
    if tmp_dir:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    for key in ("gpx_input_path", "gpx_filename", "gpx_action", "gpx_new_date"):
        context.user_data.pop(key, None)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_allowed(update):
        _cleanup(context)
        await update.message.reply_text("Cancelado.")
    return ConversationHandler.END


def get_gpx_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[MessageHandler(filters.Document.ALL, receive_gpx)],
        states={
            SELECTING_ACTION: [
                CallbackQueryHandler(handle_action, pattern="^(smooth|change_date|both)$"),
            ],
            WAITING_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_date),
            ],
        },
        fallbacks=[MessageHandler(filters.Regex(r"^/cancelar$"), cancel)],
    )
