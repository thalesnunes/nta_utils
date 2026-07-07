import logging
import tempfile
from pathlib import Path

from telegram import Update
from telegram.ext import ContextTypes

from nta_utils.auth import is_allowed
from nta_utils.services.gpx_transformer import fill_gaps

logger = logging.getLogger(__name__)


async def handle_gpx(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_allowed(update):
        return
    document = update.message.document
    if not document or not document.file_name.endswith(".gpx"):
        await update.message.reply_text("Por favor, envie um arquivo .gpx.")
        return

    status_msg = await update.message.reply_text("Processando...")

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
                f"Pronto! Adicionado(s) {result['interpolated']} pontos interpolados."
            )
    except Exception as e:
        logger.error("Error processing GPX: %s", e, exc_info=True)
        await status_msg.edit_text(f"Erro: {e}")
