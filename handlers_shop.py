"""هندلرهای فروشگاه: لیست پلن‌ها، جزئیات، خرید و سرویس‌های من."""

import logging

from telegram import Update
from telegram.ext import ContextTypes

import config
import database as db
import keyboards as kb
import texts
from utils import clear_state, fmt, user_mention

logger = logging.getLogger(__name__)

STATUS_FA = {
    "pending": "⏳ در انتظار تایید",
    "active": "✅ فعال",
    "rejected": "❌ رد شده (وجه عودت داده شد)",
}


def _volume_text(volume_gb: int) -> str:
    return "نامحدود ♾" if volume_gb == 0 else f"{volume_gb} گیگابایت"


# ---------------------------------------------------------------- منوی خرید

async def buy_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    clear_state(context)
    plans = await db.list_plans(active_only=True)
    if not plans:
        await update.message.reply_text(
            "😔 در حال حاضر پلنی برای فروش موجود نیست. لطفاً بعداً مراجعه کنید."
        )
        return
    await update.message.reply_text(
        "🛒 لطفاً پلن مورد نظر خود را انتخاب کنید:",
        reply_markup=kb.plans_list(plans),
    )


async def plan_details(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    plan_id = int(query.data.split("_")[1])
    plan = await db.get_plan(plan_id)
    if not plan or not plan["is_active"]:
        await query.answer("❌ این پلن در دسترس نیست.", show_alert=True)
        return

    user = await db.get_user(query.from_user.id)
    balance = user["balance"] if user else 0

    await query.edit_message_text(
        f"📦 {plan['name']}\n\n"
        f"💵 قیمت: {fmt(plan['price'])}\n"
        f"🗓 مدت: {plan['duration_days']} روز\n"
        f"📶 حجم: {_volume_text(plan['volume_gb'])}\n"
        f"📝 توضیحات: {plan['description'] or '—'}\n\n"
        f"💰 موجودی کیف پول شما: {fmt(balance)}",
        reply_markup=kb.plan_actions(plan_id),
    )


async def back_plans(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    plans = await db.list_plans(active_only=True)
    if not plans:
        await query.edit_message_text("😔 در حال حاضر پلنی برای فروش موجود نیست.")
        return
    await query.edit_message_text(
        "🛒 لطفاً پلن مورد نظر خود را انتخاب کنید:",
        reply_markup=kb.plans_list(plans),
    )


# ---------------------------------------------------------------- ثبت سفارش

async def buy_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    tg_user = query.from_user
    plan_id = int(query.data.split("_")[1])

    plan = await db.get_plan(plan_id)
    user = await db.get_user(tg_user.id)

    if not plan or not plan["is_active"]:
        await query.edit_message_text("❌ این پلن دیگر در دسترس نیست.")
        return
    if not user:
        await query.edit_message_text("⚠️ خطا: لطفاً /start را بزنید و دوباره تلاش کنید.")
        return
    if user["is_blocked"]:
        await query.edit_message_text(texts.BLOCKED)
        return

    price, balance = plan["price"], user["balance"]
    if balance < price:
        await query.edit_message_text(
            f"❌ موجودی کیف پول شما کافی نیست!\n\n"
            f"💵 قیمت پلن: {fmt(price)}\n"
            f"💰 موجودی شما: {fmt(balance)}\n"
            f"🔻 کسری: {fmt(price - balance)}\n\n"
            "ابتدا کیف پول خود را شارژ کنید 👇",
            reply_markup=kb.charge_link(),
        )
        return

    # کسر مبلغ و ثبت سفارش
    await db.update_balance(tg_user.id, -price)
    order_id = await db.create_order(tg_user.id, plan_id, price)
    await db.add_transaction(tg_user.id, -price, "purchase", order_id)

    # 🎁 هدیه دعوت: اولین خرید زیرمجموعه
    if await db.user_order_count(tg_user.id) == 1 and user.get("referrer_id"):
        ref_id = user["referrer_id"]
        await db.update_balance(ref_id, config.REFERRAL_BONUS)
        await db.add_transaction(ref_id, config.REFERRAL_BONUS, "referral", tg_user.id)
        try:
            await context.bot.send_message(
                ref_id,
                f"🎁 تبریک! اولین خرید زیرمجموعه شما انجام شد و "
                f"{fmt(config.REFERRAL_BONUS)} هدیه به کیف پول شما اضافه شد 🎉",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Referral bonus notify failed: %s", exc)

    new_balance = await db.get_user(tg_user.id)
    await query.edit_message_text(
        f"✅ سفارش شما با موفقیت ثبت شد!\n\n"
        f"🧾 شماره سفارش: {order_id}\n"
        f"📦 پلن: {plan['name']}\n"
        f"💵 مبلغ: {fmt(price)}\n"
        f"💰 موجودی فعلی: {fmt(new_balance['balance'])}\n\n"
        "⏳ سفارش شما در انتظار تایید است. بعد از تایید، کانفیگ در بخش "
        "«📦 سرویس‌های من» قرار می‌گیرد."
    )

    admin_text = (
        f"🛒 سفارش جدید #{order_id}\n\n"
        f"👤 {user_mention(user)}\n"
        f"🆔 آیدی عددی: {tg_user.id}\n"
        f"📦 پلن: {plan['name']}\n"
        f"💵 مبلغ: {fmt(price)}"
    )
    for admin_id in config.ADMIN_IDS:
        try:
            await context.bot.send_message(
                admin_id, admin_text, reply_markup=kb.order_review(order_id)
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("Admin notify failed (%s): %s", admin_id, exc)


# ---------------------------------------------------------------- سرویس‌های من

async def my_services(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    clear_state(context)
    orders = await db.list_user_orders(update.effective_user.id)
    if not orders:
        await update.message.reply_text(
            "📭 شما هنوز سرویسی ندارید.\n"
            "از بخش «🛒 خرید سرویس» اولین سرویس خود را تهیه کنید."
        )
        return

    sections = []
    for o in orders:
        status = STATUS_FA.get(o["status"], o["status"])
        date = (o["created_at"] or "")[:16]
        section = (
            f"🧾 سفارش #{o['id']} — {status}\n"
            f"📦 پلن: {o.get('plan_name') or 'حذف‌شده'}\n"
            f"💵 مبلغ: {fmt(o['price'])} | 🗓 {date}"
        )
        if o["status"] == "active" and o.get("config_text"):
            section += f"\n\n🔗 کانفیگ شما (لمس کنید و کپی کنید):\n{o['config_text']}"
        sections.append(section)

    # جلوگیری از پیام‌های بیش از حد طولانی تلگرام
    chunk = ""
    for section in sections:
        if len(chunk) + len(section) > 3500:
            await update.message.reply_text(chunk)
            chunk = ""
        chunk += section + "\n\n〰〰〰〰〰\n\n"
    if chunk:
        await update.message.reply_text(chunk)
