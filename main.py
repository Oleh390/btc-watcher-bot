import os
import asyncio
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram import Update, Bot
from news_handler import fetch_all_news, format_news_message
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = int(os.getenv("TELEGRAM_USER_ID"))

# Ручная команда
async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    news_list = fetch_all_news()
    for item in news_list:
        msg = format_news_message(item)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode="HTML")

# Фоновый цикл новостей
async def news_scheduler(application):
    while True:
        news_list = fetch_all_news()
        for item in news_list:
            msg = format_news_message(item)
            await application.bot.send_message(chat_id=CHAT_ID, text=msg, parse_mode="HTML")
        await asyncio.sleep(600)

async def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("news", news_command))

    # Запускаем планировщик как отдельную задачу
    asyncio.create_task(news
