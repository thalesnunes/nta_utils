from telegram import Update

from nta_utils.config import TELEGRAM_ALLOWED_USERS


def is_allowed(update: Update) -> bool:
    if not TELEGRAM_ALLOWED_USERS:
        return True
    user_id = update.effective_user.id if update.effective_user else None
    return user_id in TELEGRAM_ALLOWED_USERS if user_id else False
