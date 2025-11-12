import os
import logging
from flask import Flask, request
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai

# --- Конфигурация ---
TELEGRAM_TOKEN = "8323894251:AAFRGQiIQm2_DQTkBACCOZOW6PgyDaFA9HU"
GEMINI_API_KEY = "AIzaSyBiAl5WbG7fIyOJpCqL9-WpSNOYISfQ5mY"
WEBHOOK_URL = "https://synapse-y6kt.onrender.com/webhook"
AUTHORIZED_USERS = {"bear1berry", "AraBysh"}

# Настройка Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

# Flask для webhook
app = Flask(__name__)

# Логирование
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("logs/synapse.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- Telegram bot ---
application = Application.builder().token(TELEGRAM_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username
    if user not in AUTHORIZED_USERS:
        await update.message.reply_text("⛔ Доступ запрещён.")
        return
    await update.message.reply_html("🌑 <b>Synapse</b> активирован.
Введите ваш запрос.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username
    if user not in AUTHORIZED_USERS:
        await update.message.reply_text("⛔ У вас нет доступа.")
        return
    user_message = update.message.text
    logger.info(f"Сообщение от {user}: {user_message}")
    try:
        response = model.generate_content(user_message)
        await update.message.reply_text(response.text if response and response.text else "Пустой ответ.")
    except Exception as e:
        logger.error(f"Ошибка Gemini: {e}")
        await update.message.reply_text("⚠️ Ошибка при обработке запроса.")

application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# --- Webhook маршруты ---
@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update = Update.de_json(request.get_json(force=True), application.bot)
        application.update_queue.put_nowait(update)
    except Exception as e:
        logger.error(f"Ошибка webhook: {e}")
    return "ok", 200

@app.route("/")
def index():
    return "🌑 Synapse online", 200

if __name__ == "__main__":
    import asyncio
    async def main():
        await application.bot.set_webhook(WEBHOOK_URL)
        logger.info(f"Webhook установлен: {WEBHOOK_URL}")
    asyncio.run(main())
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
