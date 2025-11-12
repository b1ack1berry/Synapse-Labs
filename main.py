import logging
import os
from flask import Flask, request
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import google.generativeai as genai

# Настройки логирования
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Настройки API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBHOOK_URL = "https://synapse-y6kt.onrender.com/webhook"

# Авторизация Gemini
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("gemini-1.5-pro")

# Flask сервер для webhook
app = Flask(__name__)
application = ApplicationBuilder().token(BOT_TOKEN).build()

# Команда /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username
    if user not in ["bear1berry", "AraBysh"]:
        await update.message.reply_text("🚫 Доступ запрещён.")
        logger.warning(f"Попытка доступа от {user}")
        return

    await update.message.reply_html(
        "🌑 <b>Synapse</b> активирован.
"
        "🔗 Webhook подключен.
"
        "💾 Логирование активно."
    )
    logger.info(f"Бот активирован пользователем: {user}")

# Основной обработчик сообщений
async def chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user.username
    if user not in ["bear1berry", "AraBysh"]:
        await update.message.reply_text("🚫 У вас нет доступа.")
        logger.warning(f"Запрещённый пользователь: {user}")
        return

    query = update.message.text
    logger.info(f"Запрос от {user}: {query}")

    try:
        response = model.generate_content(query)
        await update.message.reply_text(response.text)
        logger.info(f"Ответ отправлен пользователю {user}")
    except Exception as e:
        await update.message.reply_text("⚠️ Ошибка при обработке запроса.")
        logger.error(f"Ошибка Gemini: {e}")

# Flask webhook route
@app.route("/webhook", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), application.bot)
    application.update_queue.put_nowait(update)
    return "ok", 200

# Добавляем команды
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("synapse", chat))

if __name__ == "__main__":
    application.run_webhook(
        listen="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        url_path="webhook",
        webhook_url=WEBHOOK_URL
    )
    app.run(host="0.0.0.0", port=5000)
