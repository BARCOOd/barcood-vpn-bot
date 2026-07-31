"""هندلرهای پنل مدیریت: آمار، سفارش‌ها، پلن‌ها، شارژها، موجودی و پیام همگانی."""

import functools
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import Forbidden, TelegramError
from telegram.ext import ContextTypes

import config
import database as db
import keyboards as kb
from utils import clear_state, fmt, parse_int, user_mention

logger = logging.getLogger(__name__)


def admin_only(func):
    """فقط اجازه دسترسی به ادمین‌ها."""

    @functools.wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id not in config.ADMIN_IDS:
            return
        return await func(update, context)

    return wrapper


def _volume_text(volume_gb: int) -> str:
    return "نامحدود ♾" if volume_gb == 0 else f"{volume_gb} گیگابایت"


# ---------------------------------------------------------------- ورود به پنل

@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    clear_state(context)
    await update.message.reply_text(
        "👑 به پنل مدیریت BARCOOD VPN خوش آمدید.\nیکی از گزینه‌ها را انتخاب کنید:",
        reply_markup=kb.admin_menu(),
    )


# ---------------------------------------------------------------- آمار

@admin_only
async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    clear_state(context)
    s = await db.get_stats()
    await update.message.reply_text(
        "📊 آمار ربات\n\n"
        f"👥 کاربران: {s['users']} نفر (🚫 مسدود: {s['blocked']})\n"
        f"🗂 پلن‌های فعال: {s['plans_active']}\n\n"
        f"🛒 کل سفارش‌ها: {s['orders']}\n"
        f"   ⏳ در انتظار: {s['orders_pending']} | ✅ فعال: {s['orders_active']}\n\n"
        f"💰 درآمد کل (خریدها): {fmt(s['revenue'])}\n"
        f"💵 مجموع شارژهای تاییدشده: {fmt(s['charged'])}\n"
        f"🧾 درخواست‌های شارژ در انتظار: {s['charges_pending']}"
    )


# ---------------------------------------------------------------- سفارش‌های در انتظار

@admin_only
async def pending_orders(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    clear_state(context)
    orders = await db.list_pending_orders()
    if not orders:
        await update.message.reply_text("📋 سفارش در انتظاری وجود ندارد.")
        return
    await update.message.reply_text(f"📋 {len(orders)} سفارش در انتظار بررسی:")
    for o in orders:
        await update.message.reply_text(
            f"🛒 سفارش #{o['id']}\n\n"
            f"👤 {user_mention(o)}\n"
            f"🆔 آیدی عددی: {o['user_id']}\n"
            f"📦 پلن: {o.get('plan_name') or 'حذف‌شده'}\n"
            f"💵 مبلغ: {fmt(o['price'])}\n"
            f"🗓 {(o['created_at'] or '')[:16]}",
            reply_markup=kb.order_review(o["id"]),
        )


@admin_only
async def order_ok(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """تایید سفارش → درخواست کانفیگ از ادمین."""
    query = update.callback_query
    await query.answer()
    order_id = int(query.data.split("_")[2])
    order = await db.get_order(order_id)
    if not order or order["status"] != "pending":
        await query.answer("⚠️ این سفارش قبلاً رسیدگی شده است.", show_alert=True)
        return
    context.user_data["expect"] = f"order_config:{order_id}"
    context.user_data["order_src"] = (
        query.message.chat_id,
        query.message.message_id,
        (query.message.text or "")[:3500],
    )
    await query.message.reply_text(
        f"🔗 لطفاً کانفیگ سرویس برای سفارش #{order_id} را ارسال کنید (متن/لینک):\n\n"
        "برای لغو /cancel را بفرستید."
    )


async def order_config_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دریافت کانفیگ از ادمین و تحویل به کاربر."""
    if update.effective_user.id not in config.ADMIN_IDS:
        return
    expect = context.user_data.get("expect", "")
    order_id = int(expect.split(":")[1])
    config_text = update.message.text.strip()
    order = await db.get_order(order_id)
    src = context.user_data.get("order_src")
    clear_state(context)

    if not order or order["status"] != "pending":
        await update.message.reply_text("⚠️ این سفارش قبلاً رسیدگی شده است.")
        return

    await db.deliver_order(order_id, config_text)

    # تحویل به کاربر — کانفیگ در پیام جداگانه و متن ساده تا راحت کپی شود
    try:
        await context.bot.send_message(
            order["user_id"],
            f"✅ سفارش #{order_id} تایید شد و سرویس شما فعال شد 🎉\n\n"
            f"📦 پلن: {order.get('plan_name') or '—'}\n"
            "🔗 کانفیگ شما:\n\n"
            f"{config_text}\n\n"
            "📚 راهنمای اتصال: منوی اصلی ← «📚 راهنمای اتصال»\n"
            "📦 مشاهده مجدد: «📦 سرویس‌های من»",
        )
    except TelegramError as exc:
        await update.message.reply_text(f"⚠️ کانفیگ ثبت شد ولی ارسال به کاربر ناموفق بود: {exc}")

    # علامت‌گذاری پیام اصلی سفارش
    if src:
        chat_id, msg_id, original = src
        try:
            await context.bot.edit_message_text(
                text=original + "\n\n✅ تایید و تحویل شد",
                chat_id=chat_id,
                message_id=msg_id,
            )
        except TelegramError:
            pass

    await update.message.reply_text(f"✅ کانفیگ سفارش #{order_id} برای کاربر ارسال شد.")


@admin_only
async def order_no(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """رد سفارش و عودت وجه به کیف پول کاربر."""
    query = update.callback_query
    await query.answer()
    admin = query.from_user
    order_id = int(query.data.split("_")[2])
    order = await db.get_order(order_id)
    if not order or order["status"] != "pending":
        await query.answer("⚠️ این سفارش قبلاً رسیدگی شده است.", show_alert=True)
        return

    await db.reject_order(order_id)
    new_balance = await db.update_balance(order["user_id"], order["price"])
    await db.add_transaction(order["user_id"], order["price"], "refund", order_id)

    await query.edit_message_text(
        (query.message.text or "")[:3500] + f"\n\n❌ توسط ادمین رد شد و وجه عودت داده شد. ({admin.full_name})"
    )
    try:
        await context.bot.send_message(
            order["user_id"],
            f"❌ سفارش #{order_id} رد شد و مبلغ {fmt(order['price'])} به کیف پول شما عودت داده شد.\n"
            f"💰 موجودی فعلی: {fmt(new_balance)}\n\n"
            "در صورت سوال با «🎧 پشتیبانی» در تماس باشید.",
        )
    except TelegramError as exc:
        logger.warning("Order reject notify failed: %s", exc)


# ---------------------------------------------------------------- درخواست‌های شارژ

@admin_only
async def pending_charges(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    clear_state(context)
    charges = await db.list_pending_charges()
    if not charges:
        await update.message.reply_text("💳 درخواست شارژ در انتظاری وجود ندارد.")
        return
    await update.message.reply_text(f"💳 {len(charges)} درخواست شارژ در انتظار بررسی:")
    for c in charges:
        caption = (
            f"🧾 درخواست شارژ #{c['id']}\n\n"
            f"👤 {user_mention(c)}\n"
            f"🆔 آیدی عددی: {c['user_id']}\n"
            f"💵 مبلغ: {fmt(c['amount'])}\n"
            f"🗓 {(c['created_at'] or '')[:16]}"
        )
        if c.get("receipt_file_id"):
            await update.message.reply_photo(
                c["receipt_file_id"], caption=caption, reply_markup=kb.charge_review(c["id"])
            )
        else:
            await update.message.reply_text(caption, reply_markup=kb.charge_review(c["id"]))


async def _handle_charge_review(query, context, approve: bool) -> None:
    req_id = int(query.data.split("_")[2])
    req = await db.get_charge_request(req_id)
    if not req or req["status"] != "pending":
        await query.answer("⚠️ این درخواست قبلاً رسیدگی شده است.", show_alert=True)
        return

    admin = query.from_user
    if approve:
        await db.set_charge_status(req_id, "approved", admin.id)
        new_balance = await db.update_balance(req["user_id"], req["amount"])
        await db.add_transaction(req["user_id"], req["amount"], "charge", req_id)
        mark = f"\n\n✅ تایید شد توسط {admin.full_name}"
        user_msg = (
            f"✅ درخواست شارژ #{req_id} تایید شد 🎉\n"
            f"💵 مبلغ {fmt(req['amount'])} به کیف پول شما اضافه شد.\n"
            f"💰 موجودی فعلی: {fmt(new_balance)}"
        )
    else:
        await db.set_charge_status(req_id, "rejected", admin.id)
        mark = f"\n\n❌ رد شد توسط {admin.full_name}"
        user_msg = (
            f"❌ درخواست شارژ #{req_id} رد شد.\n"
            "در صورت سوال با «🎧 پشتیبانی» در تماس باشید."
        )

    original = query.message.caption if query.message.photo else query.message.text
    try:
        if query.message.photo:
            await query.edit_message_caption(caption=((original or "") + mark)[:1024])
        else:
            await query.edit_message_text(text=((original or "") + mark)[:4096])
    except TelegramError:
        pass

    try:
        await context.bot.send_message(req["user_id"], user_msg)
    except TelegramError as exc:
        logger.warning("Charge review notify failed: %s", exc)


@admin_only
async def charge_ok(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    await _handle_charge_review(update.callback_query, context, approve=True)


@admin_only
async def charge_no(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.callback_query.answer()
    await _handle_charge_review(update.callback_query, context, approve=False)


# ---------------------------------------------------------------- مدیریت پلن‌ها

async def _plans_admin_view() -> tuple[str, InlineKeyboardMarkup | None]:
    plans = await db.list_plans(active_only=False)
    if not plans:
        return "🗂 هیچ پلنی ثبت نشده است. از «➕ افزودن پلن» استفاده کنید.", None
    lines, buttons = [], []
    for p in plans:
        status = "✅ فعال" if p["is_active"] else "⛔ غیرفعال"
        lines.append(
            f"#{p['id']} — {p['name']}\n"
            f"💵 {fmt(p['price'])} | 🗓 {p['duration_days']} روز | "
            f"📶 {_volume_text(p['volume_gb'])} | {status}"
        )
        toggle_label = "🔕 غیرفعال‌سازی" if p["is_active"] else "🔔 فعال‌سازی"
        buttons.append(
            [
                InlineKeyboardButton(toggle_label, callback_data=f"plan_toggle_{p['id']}"),
                InlineKeyboardButton("🗑 حذف", callback_data=f"plan_del_{p['id']}"),
            ]
        )
    return "🗂 مدیریت پلن‌ها:\n\n" + "\n\n".join(lines), InlineKeyboardMarkup(buttons)


@admin_only
async def plans_manage(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    clear_state(context)
    text, markup = await _plans_admin_view()
    await update.message.reply_text(text, reply_markup=markup)


@admin_only
async def plan_toggle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    plan_id = int(query.data.split("_")[2])
    plan = await db.get_plan(plan_id)
    if not plan:
        await query.answer("پلن یافت نشد.", show_alert=True)
        return
    await db.set_plan_active(plan_id, not plan["is_active"])
    text, markup = await _plans_admin_view()
    try:
        await query.edit_message_text(text=text, reply_markup=markup)
    except TelegramError:
        pass


@admin_only
async def plan_delete(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    plan_id = int(query.data.split("_")[2])
    if await db.count_plan_orders(plan_id) > 0:
        await query.answer(
            "⚠️ این پلن سفارش ثبت‌شده دارد؛ به‌جای حذف آن را غیرفعال کنید.",
            show_alert=True,
        )
        return
    await db.delete_plan(plan_id)
    await query.answer("🗑 پلن حذف شد.")
    text, markup = await _plans_admin_view()
    try:
        await query.edit_message_text(text=text, reply_markup=markup)
    except TelegramError:
        pass


# ------------------------------------------- افزودن پلن (گفتگوی چندمرحله‌ای)

@admin_only
async def add_plan_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    clear_state(context)
    context.user_data["plan_draft"] = {}
    context.user_data["expect"] = "plan_name"
    await update.message.reply_text(
        "➕ افزودن پلن جدید — مرحله ۱ از ۵\n\n📝 نام پلن را وارد کنید:"
        "\n(برای لغو /cancel)"
    )


async def plan_step_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """پردازش مراحل افزودن پلن. مقدار True یعنی پیام مصرف شد."""
    if update.effective_user.id not in config.ADMIN_IDS:
        return False
    expect = context.user_data.get("expect", "")
    draft = context.user_data.setdefault("plan_draft", {})
    text = update.message.text.strip()

    if expect == "plan_name":
        draft["name"] = text
        context.user_data["expect"] = "plan_price"
        await update.message.reply_text("مرحله ۲ از ۵ — 💵 قیمت به تومان (فقط عدد):")
        return True

    if expect == "plan_price":
        value = parse_int(text)
        if value is None or value <= 0:
            await update.message.reply_text("⚠️ قیمت نامعتبر است. یک عدد مثبت وارد کنید:")
            return True
        draft["price"] = value
        context.user_data["expect"] = "plan_days"
        await update.message.reply_text("مرحله ۳ از ۵ — 🗓 مدت اعتبار (روز):")
        return True

    if expect == "plan_days":
        value = parse_int(text)
        if value is None or value <= 0:
            await update.message.reply_text("⚠️ تعداد روز نامعتبر است. یک عدد مثبت وارد کنید:")
            return True
        draft["days"] = value
        context.user_data["expect"] = "plan_volume"
        await update.message.reply_text(
            "مرحله ۴ از ۵ — 📶 حجم (گیگابایت)\nعدد 0 یعنی نامحدود:"
        )
        return True

    if expect == "plan_volume":
        value = parse_int(text)
        if value is None or value < 0:
            await update.message.reply_text("⚠️ حجم نامعتبر است. یک عدد صفر یا بیشتر وارد کنید:")
            return True
        draft["volume"] = value
        context.user_data["expect"] = "plan_desc"
        await update.message.reply_text("مرحله ۵ از ۵ — 📝 توضیحات کوتاه پلن:")
        return True

    if expect == "plan_desc":
        draft["desc"] = text
        context.user_data["expect"] = None
        await update.message.reply_text(
            "🔎 پیش‌نمایش پلن:\n\n"
            f"📦 نام: {draft['name']}\n"
            f"💵 قیمت: {fmt(draft['price'])}\n"
            f"🗓 مدت: {draft['days']} روز\n"
            f"📶 حجم: {_volume_text(draft['volume'])}\n"
            f"📝 توضیحات: {draft['desc']}\n\n"
            "ذخیره شود؟",
            reply_markup=kb.plan_confirm(),
        )
        return True

    return False


@admin_only
async def plan_save(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    draft = context.user_data.pop("plan_draft", None)
    if not draft or "desc" not in draft:
        await query.edit_message_text("⚠️ داده‌ای برای ذخیره نیست. دوباره تلاش کنید.")
        return
    plan_id = await db.add_plan(
        draft["name"], draft["desc"], draft["price"], draft["days"], draft["volume"]
    )
    await query.edit_message_text(f"✅ پلن جدید با موفقیت ذخیره شد. 🆔 شناسه: {plan_id}")


@admin_only
async def plan_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    context.user_data.pop("plan_draft", None)
    await query.edit_message_text("❌ افزودن پلن لغو شد.")


# ---------------------------------------------------------------- تغییر موجودی کاربر

@admin_only
async def balance_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    clear_state(context)
    context.user_data["expect"] = "bal_user"
    await update.message.reply_text(
        "💵 تغییر موجودی کاربر\n\n🆔 آیدی عددی کاربر را ارسال کنید:\n(برای لغو /cancel)"
    )


async def balance_step_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """پردازش مراحل تغییر موجودی. مقدار True یعنی پیام مصرف شد."""
    if update.effective_user.id not in config.ADMIN_IDS:
        return False
    expect = context.user_data.get("expect", "")

    if expect == "bal_user":
        target_id = parse_int(update.message.text)
        target = await db.get_user(target_id) if target_id else None
        if not target:
            await update.message.reply_text("⚠️ کاربری با این آیدی یافت نشد. دوباره وارد کنید:")
            return True
        context.user_data["bal_target"] = target_id
        context.user_data["expect"] = "bal_amount"
        await update.message.reply_text(
            f"👤 {user_mention(target)}\n💰 موجودی فعلی: {fmt(target['balance'])}\n\n"
            "مبلغ تغییر را وارد کنید (مثال: 50000 یا -20000):"
        )
        return True

    if expect == "bal_amount":
        delta = parse_int(update.message.text, allow_negative=True)
        target_id = context.user_data.get("bal_target")
        if delta is None or delta == 0 or not target_id:
            await update.message.reply_text("⚠️ مبلغ نامعتبر است. یک عدد غیرصفر وارد کنید:")
            return True
        target = await db.get_user(target_id)
        new_balance = target["balance"] + delta
        if new_balance < 0:
            await update.message.reply_text(
                f"⚠️ موجودی منفی می‌شود! موجودی فعلی {fmt(target['balance'])} است. دوباره وارد کنید:"
            )
            return True
        await db.update_balance(target_id, delta)
        await db.add_transaction(target_id, delta, "admin")
        clear_state(context)
        await update.message.reply_text(
            f"✅ موجودی کاربر {target_id} به مقدار {fmt(delta)} تغییر کرد.\n"
            f"💰 موجودی جدید: {fmt(new_balance)}"
        )
        try:
            sign = "➕ افزوده" if delta > 0 else "➖ کسر"
            await context.bot.send_message(
                target_id,
                f"💰 موجودی کیف پول شما توسط مدیریت تغییر کرد:\n"
                f"{sign} شد: {fmt(abs(delta))}\n"
                f"💵 موجودی فعلی: {fmt(new_balance)}",
            )
        except TelegramError:
            pass
        return True

    return False


# ---------------------------------------------------------------- پیام همگانی

@admin_only
async def broadcast_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    clear_state(context)
    context.user_data["expect"] = "broadcast_text"
    await update.message.reply_text(
        "📢 پیام همگانی\n\nمتن یا عکس (به‌همراه کپشن) پیام را ارسال کنید:\n(برای لغو /cancel)"
    )


async def broadcast_text_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if update.effective_user.id not in config.ADMIN_IDS:
        return False
    context.user_data["bc_draft"] = {"text": update.message.text}
    context.user_data["expect"] = None
    await update.message.reply_text(update.message.text)
    await update.message.reply_text(
        "☝️ پیش‌نمایش پیام بالاست. برای همه کاربران ارسال شود؟",
        reply_markup=kb.broadcast_confirm(),
    )
    return True


async def broadcast_photo_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if update.effective_user.id not in config.ADMIN_IDS:
        return False
    photo = update.message.photo[-1]
    caption = update.message.caption or ""
    context.user_data["bc_draft"] = {"photo": photo.file_id, "caption": caption}
    context.user_data["expect"] = None
    await update.message.reply_photo(photo.file_id, caption=caption)
    await update.message.reply_text(
        "☝️ پیش‌نمایش پیام بالاست. برای همه کاربران ارسال شود؟",
        reply_markup=kb.broadcast_confirm(),
    )
    return True


@admin_only
async def broadcast_send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    draft = context.user_data.pop("bc_draft", None)
    if not draft:
        await query.edit_message_text("⚠️ پیامی برای ارسال یافت نشد.")
        return
    await query.edit_message_text("⏳ در حال ارسال به کاربران...")

    sent, failed = 0, 0
    for uid in await db.get_all_user_ids():
        try:
            if draft.get("photo"):
                await context.bot.send_photo(uid, draft["photo"], caption=draft.get("caption") or None)
            else:
                await context.bot.send_message(uid, draft["text"])
            sent += 1
        except Forbidden:
            failed += 1
            await db.block_user(uid, True)
        except TelegramError as exc:
            failed += 1
            logger.warning("Broadcast to %s failed: %s", uid, exc)

    await context.bot.send_message(
        query.message.chat_id,
        f"📢 ارسال همگانی تمام شد.\n\n✅ موفق: {sent}\n❌ ناموفق/مسدود: {failed}",
        reply_markup=kb.admin_menu(),
    )


@admin_only
async def broadcast_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    context.user_data.pop("bc_draft", None)
    await query.edit_message_text("❌ ارسال همگانی لغو شد.")
