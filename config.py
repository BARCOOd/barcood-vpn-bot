"""تنظیمات ربات BARCOOD VPN — همه مقادیر از متغیرهای محیطی (.env) خوانده می‌شوند."""

import os

from dotenv import load_dotenv

load_dotenv()

# توکن ربات تلگرام (از @BotFather)
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# آیدی عددی ادمین‌ها، جدا شده با کاما → ADMIN_IDS=111111111,222222222
ADMIN_IDS = {
    int(x)
    for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",")
    if x.strip().isdigit()
}

# یوزرنیم ادمین‌ها (بدون @)، جدا شده با کاما → ADMIN_USERNAMES=SuportAdminQr,otheradmin
# جایگزین ADMIN_IDS برای وقتی که آیدی عددی نمی‌دانید؛
# با اولین پیام این کاربران به ربات، به‌صورت خودکار ادمین می‌شوند.
ADMIN_USERNAMES = {
    x.strip().lstrip("@").lower()
    for x in os.getenv("ADMIN_USERNAMES", "").split(",")
    if x.strip()
}

# اطلاعات کارت برای شارژ کارت‌به‌کارت
CARD_NUMBER = os.getenv("CARD_NUMBER", "—").strip()
CARD_HOLDER = os.getenv("CARD_HOLDER", "—").strip()

# مسیر فایل دیتابیس SQLite
DB_PATH = os.getenv("DB_PATH", "barcood.db")

# پروکسی برای شبکه‌هایی که تلگرام را مسدود کرده‌اند (اختیاری)
# مثال: socks5://127.0.0.1:1080 یا http://127.0.0.1:8080
PROXY_URL = os.getenv("PROXY_URL", "").strip() or None

# هدیه معرف به ازای اولین خرید زیرمجموعه (تومان)
REFERRAL_BONUS = int(os.getenv("REFERRAL_BONUS", "20000"))

# حداقل مبلغ شارژ کیف پول (تومان)
MIN_CHARGE = int(os.getenv("MIN_CHARGE", "10000"))

BOT_NAME = "BARCOOD VPN"
