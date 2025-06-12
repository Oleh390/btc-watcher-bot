import os
import asyncio
from telegram import Bot, Update
from telegram.ext import ApplicationBuilder, CommandHandler
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

async def news_command(update: Update, context):
    await send_news()

async def run_scheduler():
    while True:
        await send_news()
        await asyncio.sleep(600)  # 10 минут

if __name__ == '__main__':
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("news", news_command))

    # Запускаем планировщик в фоне
    asyncio.create_task(run_scheduler())

    # Запускаем самого бота (главный цикл)
    app.run_polling()
