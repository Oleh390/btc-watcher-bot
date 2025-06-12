import asyncio
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dotenv import load_dotenv
from news_handler import fetch_all_news, format_news_message

load_dotenv()

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
USER_ID = os.getenv("TELEGRAM_USER_ID")

# Команда /news — присылает только новые новости
async def news_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📥 Получена команда /news")
    news_list = fetch_all_news()
    if not news_list:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Свежих новостей пока нет.")
    for item in news_list:
        msg = format_news_message(item)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode="HTML")

# Команда /news_all — присылает все свежие новости, даже повторно
async def news_all_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("📥 Получена команда /news_all")
    news_list = fetch_all_news(force_all=True)
    if not news_list:
        await context.bot.send_message(chat_id=update.effective_chat.id, text="Нет подходящих новостей.")
    for item in news_list:
        msg = format_news_message(item)
        await context.bot.send_message(chat_id=update.effective_chat.id, text=msg, parse_mode="HTML")

# Автообновление каждые 10 минут
async def run_news_scheduler(app):
    while True:
        print("⏰ Автообновление новостей по таймеру...")
        try:
            news_list = fetch_all_news()
            for item in news_list:
                msg = format_news_message(item)
                await app.bot.send_message(chat_id=USER_ID, text=msg, parse_mode="HTML")
        except Exception as e:
            print(f"❌ Ошибка при автообновлении: {e}")
        await asyncio.sleep(600)  # 10 минут

# Основной запуск
async def main():
    app = Application.builder().token(TOKEN).build()

    # Команды
    app.add_handler(CommandHandler("news", news_command))
    app.add_handler(CommandHandler("news_all", news_all_command))

    # Фоновая задача
    asyncio.create_task(run_news_scheduler(app))

    print("✅ Бот запущен")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
