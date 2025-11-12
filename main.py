import os
import asyncio
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
import google.generativeai as genai

# === Настройки ===
TOKEN = "ТВОЙ_TELEGRAM_ТОКЕН"
GEMINI_API_KEY = "ТВОЙ_GEMINI_API_KEY"

genai.configure(api_key=GEMINI_API_KEY)

app = FastAPI()
application = ApplicationBuilder().token(TOKEN).build()

# === Команды ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 Привет! Я AI-помощник Synapse. Задай вопрос!")

# === Обработка сообщений ===
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    # Отправляем в Gemini
    model = genai.GenerativeModel("gemini-1.5-flash")
    response = model.generate_content(text)
    answer = response.text if response.text else "⚠️ Ошибка: нет ответа от Gemini."

    await update.message.reply_text(answer)

# === Регистрация ===
application.add_handler(CommandHandler("start", start))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

# === Webhook ===
@app.post("/webhook")
async def webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}

# === Тестовая проверка рендер-сервера ===
@app.get("/")
async def home():
    return {"status": "ok", "bot": "Synapse AI online ✅"}

# === Запуск бота при старте Render ===
@app.on_event("startup")
async def startup_event():
    webhook_url = f"https://{os.getenv('RENDER_EXTERNAL_HOSTNAME')}/webhook"
    await application.bot.set_webhook(webhook_url)
    print(f"Webhook установлен: {webhook_url}")
