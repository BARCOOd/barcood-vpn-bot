"""توابع کمکی مشترک بین هندلرها."""

import config

# ارقام فارسی و عربی → انگلیسی
_FA = "۰۱۲۳۴۵۶۷۸۹"
_AR = "٠١٢٣٤٥٦٧٨٩"
_TRANS = str.maketrans(_FA + _AR, "0123456789" * 2)

# آیدی‌های عددی ادمین‌هایی که از طریق یوزرنیم شناسایی شدند (در حافظه)
_resolved_admin_ids: set[int] = set()


def is_admin(tg_user) -> bool:
    """بررسی ادمین بودن بر اساس آیدی عددی یا یوزرنیم."""
    if tg_user is None:
        return False
    if tg_user.id in config.ADMIN_IDS:
        return True
    username = (tg_user.username or "").lower()
    return bool(username) and username in config.ADMIN_USERNAMES


def track_admin(tg_user) -> None:
    """اگر کاربر ادمین است، آیدی عددی‌اش را برای ارسال اعلان ذخیره می‌کند."""
    if is_admin(tg_user):
        _resolved_admin_ids.add(tg_user.id)


def admin_notify_ids() -> set[int]:
    """آیدی عددی همه ادمین‌های شناخته‌شده (برای ارسال اعلان)."""
    return config.ADMIN_IDS | _resolved_admin_ids


def parse_int(text: str, allow_negative: bool = False):
    """تبدیل ورودی کاربر به عدد صحیح.

    ارقام فارسی/عربی و جداکننده‌ها را هم می‌پذیرد.
    در صورت نامعتبر بودن مقدار، None برمی‌گرداند.
    """
    if text is None:
        return None
    t = text.strip().translate(_TRANS)
    t = t.replace("تومان", "").replace("تومن", "")
    t = t.replace(",", "").replace("٬", "").replace(" ", "")
    if allow_negative and t.startswith(("+", "-")):
        sign, digits = t[0], t[1:]
        if digits.isdigit():
            val = int(digits)
            return -val if sign == "-" else val
        return None
    if t.isdigit():
        return int(t)
    return None


def fmt(amount: int) -> str:
    """قالب‌بندی مبلغ با جداکننده هزارگان و واحد تومان."""
    return f"{amount:,} تومان"


def clear_state(context) -> None:
    """پاک کردن وضعیت گفتگو (expect) و پیش‌نویس‌های کاربر."""
    for key in (
        "expect",
        "charge_amount_val",
        "plan_draft",
        "bc_draft",
        "order_src",
        "support_src",
        "bal_target",
    ):
        context.user_data.pop(key, None)


def user_mention(user: dict) -> str:
    """نمایش نام + یوزرنیم کاربر برای پیام‌های ادمین."""
    name = user.get("full_name") or "بدون نام"
    username = user.get("username") or ""
    uname = f" (@{username})" if username else ""
    return f"{name}{uname}"
