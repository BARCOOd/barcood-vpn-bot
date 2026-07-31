"""کیبوردهای ربات (منوی کاربر، پنل ادمین و دکمه‌های شیشه‌ای)."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

# ---------------- دکمه‌های منوی کاربر ----------------
BTN_BUY = "🛒 خرید سرویس"
BTN_MY_SERVICES = "📦 سرویس‌های من"
BTN_WALLET = "💰 کیف پول"
BTN_REFERRAL = "🎁 دعوت از دوستان"
BTN_SUPPORT = "🎧 پشتیبانی"
BTN_HELP = "📚 راهنمای اتصال"
BTN_ADMIN = "👑 پنل مدیریت"

# ---------------- دکمه‌های پنل مدیریت ----------------
A_STATS = "📊 آمار"
A_PENDING_ORDERS = "📋 سفارش‌های در انتظار"
A_ADD_PLAN = "➕ افزودن پلن"
A_PLANS = "🗂 مدیریت پلن‌ها"
A_CHARGES = "💳 درخواست‌های شارژ"
A_BALANCE = "💵 تغییر موجودی کاربر"
A_BROADCAST = "📢 پیام همگانی"
A_BACK = "🔙 بازگشت به منوی اصلی"


def main_menu(is_admin: bool = False) -> ReplyKeyboardMarkup:
    rows = [
        [BTN_BUY, BTN_MY_SERVICES],
        [BTN_WALLET, BTN_REFERRAL],
        [BTN_SUPPORT, BTN_HELP],
    ]
    if is_admin:
        rows.append([BTN_ADMIN])
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


def admin_menu() -> ReplyKeyboardMarkup:
    rows = [
        [A_STATS, A_PENDING_ORDERS],
        [A_ADD_PLAN, A_PLANS],
        [A_CHARGES, A_BALANCE],
        [A_BROADCAST, A_BACK],
    ]
    return ReplyKeyboardMarkup(rows, resize_keyboard=True)


# ---------------- دکمه‌های شیشه‌ای ----------------

def plans_list(plans: list[dict]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(f'{p["name"]} — {p["price"]:,} تومان', callback_data=f'plan_{p["id"]}')]
        for p in plans
    ]
    return InlineKeyboardMarkup(buttons)


def plan_actions(plan_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🛍 خرید از کیف پول", callback_data=f"buy_{plan_id}")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="back_plans")],
        ]
    )


def charge_link() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("➕ شارژ کیف پول", callback_data="charge_wallet")]]
    )


def order_review(order_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ تایید و ارسال کانفیگ", callback_data=f"order_ok_{order_id}"),
                InlineKeyboardButton("❌ رد و عودت وجه", callback_data=f"order_no_{order_id}"),
            ]
        ]
    )


def charge_review(req_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ تایید شارژ", callback_data=f"chg_ok_{req_id}"),
                InlineKeyboardButton("❌ رد درخواست", callback_data=f"chg_no_{req_id}"),
            ]
        ]
    )


def support_reply(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("✉️ پاسخ به کاربر", callback_data=f"sup_reply_{user_id}")]]
    )


def plan_confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ ذخیره پلن", callback_data="plan_save"),
                InlineKeyboardButton("❌ انصراف", callback_data="plan_cancel"),
            ]
        ]
    )


def broadcast_confirm() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ ارسال به همه", callback_data="bc_send"),
                InlineKeyboardButton("❌ انصراف", callback_data="bc_cancel"),
            ]
        ]
    )
