"""لایه دیتابیس ربات (SQLite به‌صورت async با aiosqlite)."""

import aiosqlite

from config import DB_PATH

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id         INTEGER PRIMARY KEY,
    username        TEXT,
    full_name       TEXT,
    balance         INTEGER NOT NULL DEFAULT 0,
    referrer_id     INTEGER,
    referrals_count INTEGER NOT NULL DEFAULT 0,
    is_blocked      INTEGER NOT NULL DEFAULT 0,
    joined_at       TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS plans (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT NOT NULL,
    description   TEXT,
    price         INTEGER NOT NULL,          -- تومان
    duration_days INTEGER NOT NULL,
    volume_gb     INTEGER NOT NULL,          -- 0 یعنی نامحدود
    is_active     INTEGER NOT NULL DEFAULT 1,
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS orders (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL,
    plan_id      INTEGER NOT NULL,
    price        INTEGER NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending',  -- pending / active / rejected
    config_text  TEXT,
    created_at   TEXT NOT NULL DEFAULT (datetime('now')),
    delivered_at TEXT
);

CREATE TABLE IF NOT EXISTS charge_requests (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id         INTEGER NOT NULL,
    amount          INTEGER NOT NULL,
    receipt_file_id TEXT,
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending / approved / rejected
    handled_by      INTEGER,
    created_at      TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS transactions (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL,
    amount     INTEGER NOT NULL,               -- + شارژ / - کسر
    kind       TEXT NOT NULL,                  -- charge / purchase / refund / referral / admin
    ref_id     INTEGER,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
"""

DEFAULT_PLANS = [
    ("🥉 پلن برنزی", "۱۰ گیگابایت — ۳۰ روزه | مناسب مصرف سبک", 69000, 30, 10),
    ("🥈 پلن نقره‌ای", "۵۰ گیگابایت — ۳۰ روزه | مناسب استفاده روزمره", 149000, 30, 50),
    ("🥇 پلن طلایی", "نامحدود — ۳۰ روزه | مناسب استفاده سنگین", 249000, 30, 0),
]


# ---------------------------------------------------------------- ابزار داخلی

async def _fetchall(query: str, params: tuple = ()) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(query, params)
        rows = await cur.fetchall()
        return [dict(r) for r in rows]


async def _fetchone(query: str, params: tuple = ()) -> dict | None:
    rows = await _fetchall(query, params)
    return rows[0] if rows else None


async def _execute(query: str, params: tuple = ()) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(query, params)
        await db.commit()
        return cur.lastrowid


async def _scalar(query: str, params: tuple = ()) -> int:
    row = await _fetchone(query, params)
    return int(list(row.values())[0]) if row else 0


# ---------------------------------------------------------------- راه‌اندازی

async def init_db() -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


async def seed_default_plans() -> None:
    """اگر هیچ پلنی وجود ندارد، پلن‌های پیش‌فرض را اضافه می‌کند."""
    if await _scalar("SELECT COUNT(*) AS c FROM plans") == 0:
        async with aiosqlite.connect(DB_PATH) as db:
            await db.executemany(
                "INSERT INTO plans (name, description, price, duration_days, volume_gb) "
                "VALUES (?, ?, ?, ?, ?)",
                DEFAULT_PLANS,
            )
            await db.commit()


# ---------------------------------------------------------------- کاربران

async def get_user(user_id: int) -> dict | None:
    return await _fetchone("SELECT * FROM users WHERE user_id = ?", (user_id,))


async def upsert_user(user_id: int, username: str, full_name: str) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO users (user_id, username, full_name) VALUES (?, ?, ?)",
            (user_id, username, full_name),
        )
        await db.execute(
            "UPDATE users SET username = ?, full_name = ? WHERE user_id = ?",
            (username, full_name, user_id),
        )
        await db.commit()


async def set_referrer(user_id: int, referrer_id: int) -> None:
    await _execute(
        "UPDATE users SET referrer_id = ? WHERE user_id = ? AND referrer_id IS NULL",
        (referrer_id, user_id),
    )


async def increment_referral(referrer_id: int) -> None:
    await _execute(
        "UPDATE users SET referrals_count = referrals_count + 1 WHERE user_id = ?",
        (referrer_id,),
    )


async def update_balance(user_id: int, delta: int) -> int:
    """موجودی را به اندازه delta تغییر می‌دهد و موجودی جدید را برمی‌گرداند."""
    await _execute(
        "UPDATE users SET balance = balance + ? WHERE user_id = ?", (delta, user_id)
    )
    user = await get_user(user_id)
    return user["balance"] if user else 0


async def block_user(user_id: int, blocked: bool = True) -> None:
    await _execute(
        "UPDATE users SET is_blocked = ? WHERE user_id = ?",
        (1 if blocked else 0, user_id),
    )


async def get_all_user_ids() -> list[int]:
    rows = await _fetchall("SELECT user_id FROM users")
    return [r["user_id"] for r in rows]


# ---------------------------------------------------------------- پلن‌ها

async def add_plan(name, description, price, duration_days, volume_gb) -> int:
    return await _execute(
        "INSERT INTO plans (name, description, price, duration_days, volume_gb) "
        "VALUES (?, ?, ?, ?, ?)",
        (name, description, price, duration_days, volume_gb),
    )


async def get_plan(plan_id: int) -> dict | None:
    return await _fetchone("SELECT * FROM plans WHERE id = ?", (plan_id,))


async def list_plans(active_only: bool = True) -> list[dict]:
    q = "SELECT * FROM plans"
    if active_only:
        q += " WHERE is_active = 1"
    q += " ORDER BY price"
    return await _fetchall(q)


async def set_plan_active(plan_id: int, active: bool) -> None:
    await _execute(
        "UPDATE plans SET is_active = ? WHERE id = ?",
        (1 if active else 0, plan_id),
    )


async def delete_plan(plan_id: int) -> None:
    await _execute("DELETE FROM plans WHERE id = ?", (plan_id,))


async def count_plan_orders(plan_id: int) -> int:
    return await _scalar("SELECT COUNT(*) AS c FROM orders WHERE plan_id = ?", (plan_id,))


# ---------------------------------------------------------------- سفارش‌ها

async def create_order(user_id: int, plan_id: int, price: int) -> int:
    return await _execute(
        "INSERT INTO orders (user_id, plan_id, price) VALUES (?, ?, ?)",
        (user_id, plan_id, price),
    )


async def get_order(order_id: int) -> dict | None:
    return await _fetchone(
        "SELECT o.*, p.name AS plan_name FROM orders o "
        "LEFT JOIN plans p ON p.id = o.plan_id WHERE o.id = ?",
        (order_id,),
    )


async def list_user_orders(user_id: int, limit: int = 20) -> list[dict]:
    return await _fetchall(
        "SELECT o.*, p.name AS plan_name FROM orders o "
        "LEFT JOIN plans p ON p.id = o.plan_id "
        "WHERE o.user_id = ? ORDER BY o.id DESC LIMIT ?",
        (user_id, limit),
    )


async def list_pending_orders(limit: int = 10) -> list[dict]:
    return await _fetchall(
        "SELECT o.*, p.name AS plan_name, u.full_name, u.username FROM orders o "
        "LEFT JOIN plans p ON p.id = o.plan_id "
        "LEFT JOIN users u ON u.user_id = o.user_id "
        "WHERE o.status = 'pending' ORDER BY o.id LIMIT ?",
        (limit,),
    )


async def deliver_order(order_id: int, config_text: str) -> None:
    await _execute(
        "UPDATE orders SET status = 'active', config_text = ?, "
        "delivered_at = datetime('now') WHERE id = ?",
        (config_text, order_id),
    )


async def reject_order(order_id: int) -> None:
    await _execute("UPDATE orders SET status = 'rejected' WHERE id = ?", (order_id,))


async def user_order_count(user_id: int) -> int:
    return await _scalar("SELECT COUNT(*) AS c FROM orders WHERE user_id = ?", (user_id,))


# ---------------------------------------------------------------- شارژ کیف پول

async def create_charge_request(user_id: int, amount: int, receipt_file_id: str) -> int:
    return await _execute(
        "INSERT INTO charge_requests (user_id, amount, receipt_file_id) VALUES (?, ?, ?)",
        (user_id, amount, receipt_file_id),
    )


async def get_charge_request(req_id: int) -> dict | None:
    return await _fetchone(
        "SELECT c.*, u.full_name, u.username FROM charge_requests c "
        "LEFT JOIN users u ON u.user_id = c.user_id WHERE c.id = ?",
        (req_id,),
    )


async def set_charge_status(req_id: int, status: str, admin_id: int) -> None:
    await _execute(
        "UPDATE charge_requests SET status = ?, handled_by = ? WHERE id = ?",
        (status, admin_id, req_id),
    )


async def list_pending_charges(limit: int = 10) -> list[dict]:
    return await _fetchall(
        "SELECT c.*, u.full_name, u.username FROM charge_requests c "
        "LEFT JOIN users u ON u.user_id = c.user_id "
        "WHERE c.status = 'pending' ORDER BY c.id LIMIT ?",
        (limit,),
    )


# ---------------------------------------------------------------- تراکنش‌ها

async def add_transaction(user_id: int, amount: int, kind: str, ref_id: int | None = None) -> None:
    await _execute(
        "INSERT INTO transactions (user_id, amount, kind, ref_id) VALUES (?, ?, ?, ?)",
        (user_id, amount, kind, ref_id),
    )


# ---------------------------------------------------------------- آمار

async def get_stats() -> dict:
    return {
        "users": await _scalar("SELECT COUNT(*) AS c FROM users"),
        "blocked": await _scalar("SELECT COUNT(*) AS c FROM users WHERE is_blocked = 1"),
        "orders": await _scalar("SELECT COUNT(*) AS c FROM orders"),
        "orders_pending": await _scalar(
            "SELECT COUNT(*) AS c FROM orders WHERE status = 'pending'"
        ),
        "orders_active": await _scalar(
            "SELECT COUNT(*) AS c FROM orders WHERE status = 'active'"
        ),
        "revenue": await _scalar(
            "SELECT COALESCE(SUM(-amount),0) AS c FROM transactions "
            "WHERE kind = 'purchase' AND amount < 0"
        ),
        "charged": await _scalar(
            "SELECT COALESCE(SUM(amount),0) AS c FROM transactions WHERE kind = 'charge'"
        ),
        "charges_pending": await _scalar(
            "SELECT COUNT(*) AS c FROM charge_requests WHERE status = 'pending'"
        ),
        "plans_active": await _scalar("SELECT COUNT(*) AS c FROM plans WHERE is_active = 1"),
    }
