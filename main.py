import os
import logging
import asyncio
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai

# Настройка логов
os.makedirs("logs", exist_ok=True)
logging.basicConfig(filename="logs/bot.log", level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Flask сервер для Render
app = Flask(__name__)

@app.route("/")
def home():
    return "🤖 Synapse bot is running!"

# Настройка токенов
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
ALLOWED_USERS = ["bear1berry", "AraBysh"]

# Инициализация Gemini
genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username
    if user not in ALLOWED_USERS:
        await update.message.reply_text("🚫 Доступ запрещён.")
        return
    await update.message.reply_html("🌑 <b>Synapse</b> активирован.
Отправь сообщение, чтобы начать.")

# Команда /help
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username
    if user not in ALLOWED_USERS:
        await update.message.reply_text("🚫 Доступ запрещён.")
        return
    await update.message.reply_text("Доступные команды:\n/start — запуск\n/help — помощь\n/status — статус системы")

# Команда /status
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username
    if user not in ALLOWED_USERS:
        await update.message.reply_text("🚫 Доступ запрещён.")
        return
    await update.message.reply_text("✅ Synapse работает стабильно.")

# Обработка сообщений
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username
    if user not in ALLOWED_USERS:
        await update.message.reply_text("🚫 Доступ запрещён.")
        return

    text = update.message.text
    logging.info(f"User {user}: {text}")

    try:
        response = model.generate_content(text)
        await update.message.reply_text(response.text)
    except Exception as e:
        logging.error(f"Error: {e}")
        await update.message.reply_text("⚠️ Ошибка при обработке запроса.")

# Инициализация Telegram бота
def run_telegram_bot():
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("status", status_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    asyncio.set_event_loop(asyncio.new_event_loop())
    application.run_polling()

# Запуск в отдельном потоке
if __name__ == "__main__":
    import threading
    threading.Thread(target=run_telegram_bot).start()
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 10000)))
