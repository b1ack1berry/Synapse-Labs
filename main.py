import os
import logging
import threading
import time
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import google.generativeai as genai
from dotenv import load_dotenv

# Load env
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OWNER_USERNAME = os.getenv("OWNER_USERNAME", "bear1berry")

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
start_time = time.time()

@app.route('/')
def home():
    return "✅ Synapse (Render) — bot service is running."

# Configure Gemini (Generative AI)
if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY not set — Gemini calls will fail until you configure the key.")
else:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception as e:
        logger.error(f"Failed to configure Gemini client: {e}")

# Try to construct a model variable (best-effort)
MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")
model = None
try:
    model = genai.GenerativeModel(MODEL_NAME)
except Exception as e:
    logger.warning(f"Could not initialize specified model '{MODEL_NAME}': {e}\nBot will still run; Gemini calls may fail.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    text = (
        f"🌑 <b>Synapse</b>\n"
        f"Привет, {user.first_name}!\n\n"
        f"Я — твой AI-помощник на базе Gemini 🤖\n"
        f"Напиши сообщение, и я постараюсь ответить ⚡"
    )
    await update.message.reply_html(text)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📘 Команды:\n"
        "/start — начать\n"
        "/help — помощь\n"
        "/about — информация\n"
        "/status — статус сервиса\n"
        "/owner — контакт владельца\n"
        "/clear — очистить контекст"
    )

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Synapse AI — Telegram-бот с интеграцией Gemini. Работает 24/7.")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uptime = time.time() - start_time
    mins = int(uptime // 60)
    hours = mins // 60
    mins = mins % 60
    await update.message.reply_text(f"🧠 Synapse active\n⏱ Uptime: {hours}h {mins}m")

async def owner(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"👑 Владелец: @{OWNER_USERNAME}")

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("🧹 Контекст очищен.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    username = update.effective_user.username or "user"
    logger.info(f"Received from @{username}: {text}")
    global model
    if model is None:
        await update.message.reply_text("⚠️ Gemini модель не настроена. Проверьте GEMINI_API_KEY и GEMINI_MODEL.")
        return
    try:
        # Best-effort call — library behavior may change; keep safe fallback
        response = model.generate_content(text)
        # response may be complex object; attempt to extract text
        reply = None
        if hasattr(response, 'text') and response.text:
            reply = response.text
        elif isinstance(response, dict) and response.get('candidates'):
            # older formats
            cands = response['candidates']
            if len(cands) and isinstance(cands[0], dict):
                reply = cands[0].get('content') or str(cands[0])
            else:
                reply = str(cands[0])
        else:
            reply = str(response)
        await update.message.reply_text(reply)
    except Exception as e:
        logger.error(f"Gemini call failed: {e}")
        await update.message.reply_text("❌ Ошибка при обращении к Gemini. Смотри логи.")

def run_telegram_bot():
    if not TELEGRAM_TOKEN:
        logger.error("TELEGRAM_TOKEN not set — bot cannot start.")
        return
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('help', help_command))
    application.add_handler(CommandHandler('about', about))
    application.add_handler(CommandHandler('status', status))
    application.add_handler(CommandHandler('owner', owner))
    application.add_handler(CommandHandler('clear', clear))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info('Starting Telegram polling...')
    application.run_polling()

if __name__ == '__main__':
    bot_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    bot_thread.start()
    port = int(os.getenv('PORT', 10000))
    app.run(host='0.0.0.0', port=port)
