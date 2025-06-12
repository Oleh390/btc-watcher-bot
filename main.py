import os
import asyncio
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from news_handler import fetch_all_news, format_news_message
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("TELEGRAM_USER_ID"))

bot = Bot(token=TOKEN)

async def send_news():
    news_list = fetch_all_news()
    for item in news_list:
        msg = format_news_message(item)
        await bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="HTML")

# Команда вручную
async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await send_news()

# Фоновая задача каждые 10 минут
async def news_scheduler(app):
    while True:
        await send_news()
        await asyncio.sleep(600)

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("news", news_command))

    # запускаем фоновую задачу
    app.create_task(news_scheduler(app))

    # запускаем самого бота
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
