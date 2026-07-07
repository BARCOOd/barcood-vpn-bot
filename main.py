from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
import os

TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 به ربات BARCOOD VPN خوش آمدید.\n\n"
        "ربات در حال راه‌اندازی است و به‌زودی امکانات کامل فعال می‌شود."
    )

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    print("Bot Started...")
    app.run_polling()

if __name__ == "__main__":
    main()
