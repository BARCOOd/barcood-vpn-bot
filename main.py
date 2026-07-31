"""نقطه ورود ربات BARCOOD VPN — اتصال همه هندلرها و اجرای ربات."""

import logging
import re

from telegram.error import InvalidToken
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

import config
import handlers_admin as admin
import handlers_shop as shop
import handlers_support as support
import handlers_user as user
import keyboards as kb
from database import init_db, seed_default_plans
from handlers_router import photo_router, text_router
from utils import track_admin

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


def _btn(button_text: str, handler) -> MessageHandler:
    """هندلر دکمه‌های کیبورد (مطابقت دقیق متن دکمه)."""
    return MessageHandler(filters.Regex(f"^{re.escape(button_text)}$"), handler)


def build_app() -> Application:
    builder = Application.builder().token(config.BOT_TOKEN)
    if config.PROXY_URL:
        # برای شبکه‌هایی که api.telegram.org را مسدود کرده‌اند
        builder = builder.proxy(config.PROXY_URL).get_updates_proxy(config.PROXY_URL)
    app = builder.build()

    # ---------------- دستورها ----------------
    app.add_handler(CommandHandler("start", user.start))
    app.add_handler(CommandHandler("cancel", user.cancel))
    app.add_handler(CommandHandler("admin", admin.admin_panel))

    # ---------------- منوی کاربر ----------------
    app.add_handler(_btn(kb.BTN_BUY, shop.buy_menu))
    app.add_handler(_btn(kb.BTN_MY_SERVICES, shop.my_services))
    app.add_handler(_btn(kb.BTN_WALLET, user.wallet))
    app.add_handler(_btn(kb.BTN_REFERRAL, user.referral))
    app.add_handler(_btn(kb.BTN_SUPPORT, support.support_start))
    app.add_handler(_btn(kb.BTN_HELP, user.help_))
    app.add_handler(_btn(kb.BTN_ADMIN, admin.admin_panel))

    # ---------------- منوی مدیریت ----------------
    app.add_handler(_btn(kb.A_STATS, admin.stats))
    app.add_handler(_btn(kb.A_PENDING_ORDERS, admin.pending_orders))
    app.add_handler(_btn(kb.A_ADD_PLAN, admin.add_plan_start))
    app.add_handler(_btn(kb.A_PLANS, admin.plans_manage))
    app.add_handler(_btn(kb.A_CHARGES, admin.pending_charges))
    app.add_handler(_btn(kb.A_BALANCE, admin.balance_start))
    app.add_handler(_btn(kb.A_BROADCAST, admin.broadcast_start))
    app.add_handler(_btn(kb.A_BACK, user.home))

    # ---------------- دکمه‌های شیشه‌ای (کاربر) ----------------
    app.add_handler(CallbackQueryHandler(shop.plan_details, pattern=r"^plan_\d+$"))
    app.add_handler(CallbackQueryHandler(shop.back_plans, pattern=r"^back_plans$"))
    app.add_handler(CallbackQueryHandler(shop.buy_confirm, pattern=r"^buy_\d+$"))
    app.add_handler(CallbackQueryHandler(user.charge_start, pattern=r"^charge_wallet$"))

    # ---------------- دکمه‌های شیشه‌ای (ادمین) ----------------
    app.add_handler(CallbackQueryHandler(admin.order_ok, pattern=r"^order_ok_\d+$"))
    app.add_handler(CallbackQueryHandler(admin.order_no, pattern=r"^order_no_\d+$"))
    app.add_handler(CallbackQueryHandler(admin.charge_ok, pattern=r"^chg_ok_\d+$"))
    app.add_handler(CallbackQueryHandler(admin.charge_no, pattern=r"^chg_no_\d+$"))
    app.add_handler(CallbackQueryHandler(admin.plan_toggle, pattern=r"^plan_toggle_\d+$"))
    app.add_handler(CallbackQueryHandler(admin.plan_delete, pattern=r"^plan_del_\d+$"))
    app.add_handler(CallbackQueryHandler(admin.plan_save, pattern=r"^plan_save$"))
    app.add_handler(CallbackQueryHandler(admin.plan_cancel, pattern=r"^plan_cancel$"))
    app.add_handler(CallbackQueryHandler(admin.broadcast_send, pattern=r"^bc_send$"))
    app.add_handler(CallbackQueryHandler(admin.broadcast_cancel, pattern=r"^bc_cancel$"))
    app.add_handler(CallbackQueryHandler(support.admin_support_reply, pattern=r"^sup_reply_\d+$"))

    # ---------------- ردیابی خودکار ادمین‌ها (یوزرنیم → آیدی عددی) ----------------
    async def _track(update, context) -> None:
        if update.effective_user:
            track_admin(update.effective_user)

    app.add_handler(MessageHandler(filters.ALL, _track), group=-1)

    # ---------------- مسیریاب ورودی‌ها (آخرین‌ها) ----------------
    app.add_handler(MessageHandler(filters.PHOTO & ~filters.COMMAND, photo_router))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_router))

    # آماده‌سازی دیتابیس داخل حلقه رویداد خود ربات (قبل از شروع polling)
    async def _post_init(application: Application) -> None:
        await bootstrap()

    app.post_init = _post_init
    return app


async def bootstrap() -> None:
    """آماده‌سازی دیتابیس قبل از اجرا (ساخت جداول + پلن‌های نمونه)."""
    await init_db()
    await seed_default_plans()


def main() -> None:
    if not config.BOT_TOKEN or not re.fullmatch(r"\d{5,}:[\w-]{30,}", config.BOT_TOKEN):
        raise SystemExit(
            "❌ متغیر BOT_TOKEN در فایل .env تنظیم نشده یا معتبر نیست.\n"
            "   ۱) از @BotFather توکن بگیرید (شکل: 123456789:AAAA...)\n"
            "   ۲) در فایل .env مقدار BOT_TOKEN را با آن جایگزین کنید."
        )
    if not config.ADMIN_IDS and not config.ADMIN_USERNAMES:
        logger.warning(
            "⚠️ هیچ ادمینی تنظیم نشده است! پنل مدیریت برای هیچ‌کس فعال نمی‌شود.\n"
            "   ADMIN_IDS (آیدی عددی) یا ADMIN_USERNAMES (یوزرنیم) را در .env قرار دهید."
        )

    app = build_app()
    logger.info(
        "🤖 BARCOOD VPN Bot started… (admin ids: %s | admin usernames: %s)",
        config.ADMIN_IDS or "—",
        {f"@{u}" for u in config.ADMIN_USERNAMES} or "—",
    )
    try:
        app.run_polling(allowed_updates=["message", "callback_query"])
    except InvalidToken:
        raise SystemExit(
            "❌ توکن ربات نامعتبر است. توکن صحیح را از @BotFather بگیرید و در .env قرار دهید."
        ) from None


if __name__ == "__main__":
    main()
