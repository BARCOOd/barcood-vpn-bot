"""اسکریپت تشخیص مشکلات راه‌اندازی — قبل از اجرای ربات این را اجرا کنید:

    python check_setup.py

همه مراحل را یک‌به‌یک بررسی می‌کند و در صورت مشکل، راه‌حل را فارسی می‌گوید.
"""

import asyncio
import re
import sys


def check(label: str, ok: bool, fix: str = "") -> bool:
    print(f"  {'✅' if ok else '❌'} {label}")
    if not ok and fix:
        print(f"     راه‌حل: {fix}")
    return ok


async def main() -> None:
    print("🔍 بررسی راه‌اندازی BARCOOD VPN Bot\n")

    # ---------------- مرحله ۱: وابستگی‌ها ----------------
    print("۱) بررسی کتابخانه‌ها…")
    try:
        import aiosqlite
        import httpx
        import telegram
        print(
            f"  ✅ نسخه‌ها: python-telegram-bot={telegram.__version__} | "
            f"aiosqlite={aiosqlite.__version__} | Python {sys.version.split()[0]}"
        )
    except ImportError as exc:
        check(f"کتابخانه نصب نیست: {exc.name}", False, "pip install -r requirements.txt")
        return

    # ---------------- مرحله ۲: متغیرها ----------------
    print("\n۲) بررسی فایل .env…")
    import config

    token_ok = bool(re.fullmatch(r"\d{5,}:[\w-]{30,}", config.BOT_TOKEN or ""))
    if not check("BOT_TOKEN فرمت درستی دارد", token_ok,
                 "توکن را از @BotFather بگیرید و در .env بنویسید"):
        return

    check("حداقل یک ادمین تنظیم شده",
          bool(config.ADMIN_IDS or config.ADMIN_USERNAMES),
          "ADMIN_IDS یا ADMIN_USERNAMES را در .env تنظیم کنید")

    check("CARD_NUMBER تنظیم شده", config.CARD_NUMBER != "—",
          "شماره کارت شارژ کیف پول را در .env بنویسید")

    # ---------------- مرحله ۳: اتصال به تلگرام ----------------
    print("\n۳) تست اتصال به api.telegram.org …")
    url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/getMe"
    try:
        async with httpx.AsyncClient(timeout=15, proxy=config.PROXY_URL or None) as client:
            resp = await client.get(url)
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        check("اتصال به سرور تلگرام", False,
              "اینترنت شما api.telegram.org را مسدود می‌کند.\n"
              "        ۱) ربات را روی سرور خارج از ایران (VPS) اجرا کنید، یا\n"
              "        ۲) در .env خط PROXY_URL را با یک پروکسی سالم پر کنید\n"
              "           مثال: PROXY_URL=socks5://127.0.0.1:1080")
        print(f"       جزئیات خطا: {type(exc).__name__}: {exc}")
        return

    if data.get("ok"):
        bot = data["result"]
        print(f"  ✅ توکن معتبر است — ربات: @{bot['username']}")
        print(f"     لینک ربات: https://t.me/{bot['username']}")
    else:
        check("اعتبار توکن", False,
              "توکن اشتباه است. از @BotFather با /token توکن جدید بگیرید")
        print(f"       پاسخ تلگرام: {data}")
        return

    # ---------------- مرحله ۴: دیتابیس ----------------
    print("\n۴) بررسی دیتابیس…")
    try:
        from database import init_db, list_plans
        await init_db()
        plans = await list_plans()
        print(f"  ✅ دیتابیس سالم است ({len(plans)} پلن فعال)")
    except Exception as exc:  # noqa: BLE001
        check("دیتابیس", False, f"خطا: {exc}")
        return

    print("\n🎉 همه‌چیز آماده است! حالا ربات را اجرا کنید:\n\n    python main.py\n")
    print("اگر بعد از اجرا هم ربات پاسخ نداد، خروجی ترمینال را بفرستید.")


if __name__ == "__main__":
    asyncio.run(main())
