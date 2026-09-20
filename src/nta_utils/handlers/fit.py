import asyncio
import logging
import re
import shutil
import tempfile
from pathlib import Path

from telegram import Update
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

from nta_utils.auth import is_allowed
from nta_utils.services.fit_transformer import change_fit_date

logger = logging.getLogger(__name__)

WAITING_DATE = 0


async def receive_fit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_allowed(update):
        return ConversationHandler.END

    document = update.message.document
    if not document or not document.file_name or not document.file_name.lower().endswith(".fit"):
        await update.message.reply_text("Por favor, envie um arquivo .fit.")
        return ConversationHandler.END

    file = await document.get_file()
    tmp_dir = tempfile.mkdtemp()
    input_path = Path(tmp_dir) / document.file_name
    await file.download_to_drive(input_path)

    context.user_data["fit_input_path"] = str(input_path)
    context.user_data["fit_tmp_dir"] = tmp_dir
    context.user_data["fit_filename"] = document.file_name

    await update.message.reply_text(
        f"Arquivo recebido: `{document.file_name}`\n\n"
        "Envie a nova data no formato YYYY-MM-DD (ex: 2026-08-01)",
        parse_mode="Markdown",
    )
    return WAITING_DATE


async def receive_date(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not is_allowed(update):
        return ConversationHandler.END

    text = update.message.text.strip()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        await update.message.reply_text("Formato inválido. Envie a data no formato YYYY-MM-DD (ex: 2026-08-01)")
        return WAITING_DATE

    status_msg = await update.message.reply_text("Processando...")

    try:
        input_path = Path(context.user_data["fit_input_path"])
        filename = context.user_data["fit_filename"]
        output_path = input_path.parent / f"modified_{filename}"

        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            change_fit_date,
            input_path,
            output_path,
            text,
            filename,
        )

        with open(output_path, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=result["new_filename"],
            )

        await status_msg.edit_text(
            f"Data alterada de {result['old_date']} para {result['new_date']}."
        )
    except Exception as e:
        logger.error("Error processing FIT: %s", e, exc_info=True)
        await status_msg.edit_text(f"Erro: {e}")
    finally:
        _cleanup(context)

    return ConversationHandler.END


def _cleanup(context: ContextTypes.DEFAULT_TYPE) -> None:
    tmp_dir = context.user_data.pop("fit_tmp_dir", None)
    if tmp_dir:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    for key in ("fit_input_path", "fit_filename"):
        context.user_data.pop(key, None)


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if is_allowed(update):
        _cleanup(context)
        await update.message.reply_text("Cancelado.")
    return ConversationHandler.END


def get_fit_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            MessageHandler(filters.Document.FileExtension("fit"), receive_fit),
        ],
        states={
            WAITING_DATE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_date),
            ],
        },
        fallbacks=[MessageHandler(filters.Regex(r"^/cancelar$"), cancel)],
    )
