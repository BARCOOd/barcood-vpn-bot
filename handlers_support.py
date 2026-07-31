"""هندلرهای پشتیبانی: ارسال پیام کاربر به ادمین و پاسخ ادمین به کاربر."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

import config
import database as db
import keyboards as kb
import texts
from utils import clear_state

logger = logging.getLogger(__name__)


async def support_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    clear_state(context)
    user = await db.get_user(update.effective_user.id)
    if user and user["is_blocked"]:
        await update.message.reply_text(texts.BLOCKED)
        return
    context.user_data["expect"] = "support_msg"
    await update.message.reply_text(texts.SUPPORT_INTRO)


async def _forward_to_admins(context: ContextTypes.DEFAULT_TYPE, user, payload: dict, markup) -> None:
    info = (
        f"🎧 پیام پشتیبانی\n\n"
        f"👤 {user.full_name or 'بدون نام'}"
        f"{' (@' + user.username + ')' if user.username else ''}\n"
        f"🆔 آیدی عددی: {user.id}\n\n"
    )
    for admin_id in config.ADMIN_IDS:
        try:
            if payload.get("photo"):
                await context.bot.send_photo(
                    admin_id,
                    payload["photo"],
                    caption=info + (payload.get("caption") or ""),
                    reply_markup=markup,
                )
            else:
                await context.bot.send_message(
                    admin_id, info + payload.get("text", ""), reply_markup=markup
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Support forward failed (%s): %s", admin_id, exc)


async def support_message_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دریافت متن پشتیبانی از کاربر."""
    user = update.effective_user
    clear_state(context)
    markup = kb.support_reply(user.id)
    await _forward_to_admins(context, user, {"text": update.message.text}, markup)
    await update.message.reply_text(
        "✅ پیام شما برای تیم پشتیبانی ارسال شد.\n"
        "به محض بررسی، پاسخ از همین‌جا برایتان ارسال می‌شود 🙏",
        reply_markup=kb.main_menu(user.id in config.ADMIN_IDS),
    )


async def support_photo_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دریافت عکس پشتیبانی از کاربر."""
    user = update.effective_user
    clear_state(context)
    markup = kb.support_reply(user.id)
    await _forward_to_admins(
        context,
        user,
        {"photo": update.message.photo[-1].file_id, "caption": update.message.caption or ""},
        markup,
    )
    await update.message.reply_text(
        "✅ پیام شما برای تیم پشتیبانی ارسال شد.\n"
        "به محض بررسی، پاسخ از همین‌جا برایتان ارسال می‌شود 🙏",
        reply_markup=kb.main_menu(user.id in config.ADMIN_IDS),
    )


# ---------------------------------------------------------------- پاسخ ادمین

async def admin_support_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """کلیک ادمین روی «✉️ پاسخ به کاربر»."""
    query = update.callback_query
    await query.answer()
    if query.from_user.id not in config.ADMIN_IDS:
        return
    target_id = int(query.data.split("_")[2])
    context.user_data["expect"] = f"support_reply:{target_id}"
    original = query.message.caption if query.message.photo else query.message.text
    context.user_data["support_src"] = (
        query.message.chat_id,
        query.message.message_id,
        bool(query.message.photo),
        original or "",
    )
    await query.message.reply_text(
        f"✉️ پاسخ خود به کاربر <{target_id}> را بنویسید:\n\nبرای لغو /cancel را بفرستید."
    )


async def admin_reply_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """ارسال پاسخ ادمین به کاربر."""
    expect = context.user_data.get("expect", "")
    target_id = int(expect.split(":")[1])
    reply_text = update.message.text.strip()
    src = context.user_data.get("support_src")
    clear_state(context)

    try:
        await context.bot.send_message(
            target_id, f"📩 پاسخ پشتیبانی:\n\n{reply_text}"
        )
        await update.message.reply_text("✅ پاسخ شما برای کاربر ارسال شد.")
    except Exception as exc:  # noqa: BLE001
        await update.message.reply_text(f"❌ ارسال پیام به کاربر ناموفق بود: {exc}")

    # علامت‌گذاری روی پیام اصلی که پاسخ داده شد
    if src:
        chat_id, msg_id, is_photo, original = src
        marked = original + "\n\n✅ پاسخ داده شد"
        try:
            if is_photo:
                await context.bot.edit_message_caption(
                    chat_id=chat_id, message_id=msg_id, caption=marked[:1024]
                )
            else:
                await context.bot.edit_message_text(
                    text=marked[:4096], chat_id=chat_id, message_id=msg_id
                )
        except Exception:  # noqa: BLE001,S110
            pass
