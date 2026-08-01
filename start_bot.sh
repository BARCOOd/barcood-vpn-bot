#!/usr/bin/env bash
# اجرای ربات BARCOOD VPN روی لینوکس / سرور (VPS)
set -e
cd "$(dirname "$0")"

echo "========================================"
echo "  BARCOOD VPN Bot - Linux Launcher"
echo "========================================"

# ترجیحاً محیط مجازی
if [ ! -d ".venv" ]; then
  echo "[1/4] ساخت محیط مجازی…"
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate

echo "[2/4] نصب کتابخانه‌ها…"
pip install -q -r requirements.txt --disable-pip-version-warning

echo "[3/4] بررسی سلامت راه‌اندازی…"
python check_setup.py

echo "[4/4] اجرای ربات… (برای قطع: Ctrl+C)"
exec python main.py
