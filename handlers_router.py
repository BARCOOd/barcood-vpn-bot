"""مسیریاب پیام‌های متنی/تصویری بر اساس وضعیت گفتگوی کاربر (expect)."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

import config
import handlers_admin as admin
import handlers_support as support
import handlers_user as user
import keyboards as kb

logger = logging.getLogger(__name__)


async def text_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """آخرین هندلر متنی — بر اساس مرحله گفتگو هدایت می‌کند."""
    expect = context.user_data.get("expect")
    text = update.message.text or ""

    if not expect:
        await update.message.reply_text(
            "🤖 لطفاً از دکمه‌های منوی پایین استفاده کنید:",
            reply_markup=kb.main_menu(update.effective_user.id in config.ADMIN_IDS),
        )
        return

    # ---- بخش کاربر ----
    if expect == "charge_amount":
        await user.charge_amount_received(update, context)
        return
    if expect == "charge_receipt":
        await update.message.reply_text(
            "📎 لطفاً عکس رسید را ارسال کنید (یا برای لغو /cancel)."
        )
        return
    if expect == "support_msg":
        await support.support_message_received(update, context)
        return

    # ---- مراحل چندمرحله‌ای ادمین ----
    if expect.startswith("plan_"):
        await admin.plan_step_received(update, context)
        return
    if expect.startswith("bal_"):
        await admin.balance_step_received(update, context)
        return
    if expect == "broadcast_text":
        await admin.broadcast_text_received(update, context)
        return
    if expect.startswith("order_config:"):
        if not text.strip():
            await update.message.reply_text("⚠️ کانفیگ باید متن باشد. دوباره ارسال کنید:")
            return
        await admin.order_config_received(update, context)
        return
    if expect.startswith("support_reply:"):
        await support.admin_reply_received(update, context)
        return

    # وضعیت ناشناخته — ریست
    logger.warning("Unknown expect state: %s", expect)
    context.user_data["expect"] = None
    await update.message.reply_text(
        "⚠️ خطایی رخ داد؛ به ابتدای گفتگو برگشتیم.",
        reply_markup=kb.main_menu(update.effective_user.id in config.ADMIN_IDS),
    )


async def photo_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """هندلر عکس‌ها بر اساس مرحله گفتگو."""
    expect = context.user_data.get("expect")

    if expect == "charge_receipt":
        await user.charge_receipt_received(update, context)
        return
    if expect == "support_msg":
        await support.support_photo_received(update, context)
        return
    if expect == "broadcast_text":
        await admin.broadcast_photo_received(update, context)
        return
    if expect and expect.startswith("order_config:"):
        await update.message.reply_text(
            "⚠️ کانفیگ باید به‌صورت متن ارسال شود. لطفاً متن/لینک کانفیگ را بفرستید:"
        )
        return

    await update.message.reply_text(
        "🤖 لطفاً از دکمه‌های منوی پایین استفاده کنید:",
        reply_markup=kb.main_menu(update.effective_user.id in config.ADMIN_IDS),
    )
