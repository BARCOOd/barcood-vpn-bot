"""هندلرهای بخش کاربری: شروع، کیف پول، دعوت از دوستان، راهنما، لغو."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

import config
import database as db
import keyboards as kb
import texts
from utils import admin_notify_ids, clear_state, fmt, is_admin, parse_int, user_mention

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دستور /start — ثبت کاربر، پردازش لینک دعوت و نمایش منوی اصلی."""
    clear_state(context)
    user = update.effective_user
    existing = await db.get_user(user.id)
    await db.upsert_user(user.id, user.username or "", user.full_name or "")

    # پردازش لینک دعوت: t.me/bot?start=ref_<id>
    if not existing and context.args:
        arg = context.args[0]
        if arg.startswith("ref_"):
            ref_id = parse_int(arg[4:])
            if ref_id and ref_id != user.id and await db.get_user(ref_id):
                await db.set_referrer(user.id, ref_id)
                await db.increment_referral(ref_id)
                try:
                    await context.bot.send_message(
                        ref_id,
                        f"🎉 یک کاربر جدید با لینک دعوت شما وارد ربات شد!\n"
                        f"👤 {user.full_name}\n\n"
                        f"با اولین خرید ایشان، {fmt(config.REFERRAL_BONUS)} هدیه دریافت می‌کنید 🎁",
                    )
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Referral notify failed: %s", exc)

    await update.message.reply_text(
        texts.WELCOME.format(name=user.first_name or "کاربر"),
        reply_markup=kb.main_menu(is_admin(user)),
    )


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دستور /cancel — لغو هر عملیات در جریان."""
    clear_state(context)
    await update.message.reply_text(
        "❌ عملیات لغو شد.",
        reply_markup=kb.main_menu(is_admin(update.effective_user)),
    )


async def home(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """بازگشت به منوی اصلی."""
    clear_state(context)
    await update.message.reply_text(
        "🏠 منوی اصلی:",
        reply_markup=kb.main_menu(is_admin(update.effective_user)),
    )


async def help_(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    clear_state(context)
    await update.message.reply_text(texts.HELP)


# ---------------------------------------------------------------- کیف پول

async def wallet(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    clear_state(context)
    user = await db.get_user(update.effective_user.id)
    balance = user["balance"] if user else 0
    await update.message.reply_text(
        f"💰 کیف پول شما\n\n💵 موجودی فعلی: {fmt(balance)}\n\n"
        "برای خرید سرویس، ابتدا کیف پول خود را شارژ کنید 👇",
        reply_markup=kb.charge_link(),
    )


async def charge_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """شروع فرایند شارژ کیف پول (دکمه شیشه‌ای)."""
    query = update.callback_query
    await query.answer()
    clear_state(context)
    user = await db.get_user(query.from_user.id)
    if user and user["is_blocked"]:
        await query.message.reply_text(texts.BLOCKED)
        return
    context.user_data["expect"] = "charge_amount"
    await query.message.reply_text(
        f"💵 مبلغ شارژ را به تومان وارد کنید (حداقل {fmt(config.MIN_CHARGE)}):\n\n"
        "برای لغو /cancel را بفرستید."
    )


async def charge_amount_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """مرحله دریافت مبلغ شارژ."""
    amount = parse_int(update.message.text)
    if amount is None or amount < config.MIN_CHARGE:
        await update.message.reply_text(
            f"⚠️ مبلغ نامعتبر است. لطفاً یک عدد صحیح حداقل {fmt(config.MIN_CHARGE)} وارد کنید:"
        )
        return
    context.user_data["charge_amount_val"] = amount
    context.user_data["expect"] = "charge_receipt"
    await update.message.reply_text(
        texts.CARD_INFO.format(
            amount=fmt(amount), card_number=config.CARD_NUMBER, card_holder=config.CARD_HOLDER
        )
    )


async def charge_receipt_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """مرحله دریافت عکس رسید و ثبت درخواست برای ادمین."""
    user = update.effective_user
    amount = context.user_data.pop("charge_amount_val", None)
    clear_state(context)
    if not amount:
        await update.message.reply_text("⚠️ خطایی رخ داد. لطفاً دوباره تلاش کنید.")
        return

    photo = update.message.photo[-1]
    req_id = await db.create_charge_request(user.id, amount, photo.file_id)
    await db.upsert_user(user.id, user.username or "", user.full_name or "")

    await update.message.reply_text(
        f"✅ رسید شما ثبت شد و در انتظار تایید ادمین است.\n\n"
        f"🧾 شماره درخواست: {req_id}\n"
        f"💵 مبلغ: {fmt(amount)}\n\n"
        "نتیجه از طریق همین ربات به شما اطلاع‌رسانی می‌شود 🙏",
        reply_markup=kb.main_menu(is_admin(user)),
    )

    caption = (
        f"🧾 درخواست شارژ کیف پول #{req_id}\n\n"
        f"👤 {user_mention({'full_name': user.full_name, 'username': user.username})}\n"
        f"🆔 آیدی عددی: {user.id}\n"
        f"💵 مبلغ: {fmt(amount)}"
    )
    for admin_id in admin_notify_ids():
        try:
            await context.bot.send_photo(
                admin_id, photo.file_id, caption=caption, reply_markup=kb.charge_review(req_id)
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Admin notify failed (%s): %s", admin_id, exc)


# ---------------------------------------------------------------- دعوت از دوستان

async def referral(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    clear_state(context)
    user = update.effective_user
    record = await db.get_user(user.id)
    count = record["referrals_count"] if record else 0

    if "bot_username" not in context.bot_data:
        me = await context.bot.get_me()
        context.bot_data["bot_username"] = me.username
    link = f"https://t.me/{context.bot_data['bot_username']}?start=ref_{user.id}"

    await update.message.reply_text(
        texts.REFERRAL.format(bonus=fmt(config.REFERRAL_BONUS), link=link, count=count)
    )
