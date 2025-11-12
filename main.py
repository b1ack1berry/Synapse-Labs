import os
import logging
import requests
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

# Загружаем переменные окружения из файла .env
load_dotenv()

# Конфигурационные переменные
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", 512))  # Максимальное количество токенов
TIMEOUT = int(os.getenv("TIMEOUT", 30))  # Таймаут для запросов

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("Необходимые переменные окружения TELEGRAM_TOKEN и OPENAI_API_KEY отсутствуют. См. пример .env.")

# Инициализация FastAPI
app = FastAPI(title="Synapse Telegram Webhook (FastAPI)")


# Модель для обработки обновлений Telegram
class UpdateModel(BaseModel):
    update_id: Optional[int] = None
    message: Optional[dict] = None
    edited_message: Optional[dict] = None


# Функция для запроса к OpenAI API
def call_openai_chat(prompt: str, system_prompt: Optional[str] = None) -> str:
    """
    Запрос к OpenAI API (Chat Completions).
    Возвращает ответ от ассистента (строка).
    """
    url = "https://api.openai.com/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
    }
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": OPENAI_MODEL,
        "messages": messages,
        "max_tokens": MAX_TOKENS,
        "temperature": 0.7,
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=TIMEOUT)
        r.raise_for_status()
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        return content.strip()
    except requests.exceptions.RequestException as e:
        logging.exception("Запрос к OpenAI не удался: %s", str(e))
        return "Извините, произошла ошибка при обработке запроса в OpenAI."


# Функция для отправки сообщения в Telegram
def send_telegram_message(chat_id: int, text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=TIMEOUT)
        r.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        logging.exception("Не удалось отправить сообщение в Telegram: %s", str(e))
        return False


# Событие старта приложения FastAPI (установка webhook для Telegram)
@app.on_event("startup")
def startup_event():
    if TELEGRAM_WEBHOOK_URL:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
        try:
            r = requests.post(url, json={"url": TELEGRAM_WEBHOOK_URL}, timeout=TIMEOUT)
            r.raise_for_status()
            logging.info("Ответ при установке webhook: %s", r.text)
        except Exception:
            logging.exception("Не удалось установить webhook для Telegram")


# Здоровье сервиса — проверка доступности
@app.get("/", tags=["health"])
async def root():
    return {"status": "ok", "service": "synapse-telegram-webhook"}


# Вебхук для получения сообщений от Telegram
@app.post("/webhook")
async def webhook(request: Request):
    """
    Обрабатывает обновления Telegram (входящие сообщения и измененные сообщения).
    Реализовано вручную без использования python-telegram-bot для минимальных зависимостей.
    """
    try:
        payload = await request.json()
    except Exception as e:
        logging.exception("Неверный JSON в запросе вебхука")
        raise HTTPException(status_code=400, detail="Неверный формат JSON")

    update = UpdateModel(**payload)
    tg_message = update.message or update.edited_message
    if not tg_message:
        return {"ok": True, "note": "Нет сообщения для обработки"}

    chat = tg_message.get("chat", {})
    chat_id = chat.get("id")
    text = tg_message.get("text") or tg_message.get("caption") or ""
    if not chat_id or not text:
        return {"ok": True, "note": "Нет текста или chat_id"}

    # Простая обработка команд
    if text.startswith("/start"):
        send_telegram_message(chat_id, "🌑 <b>Synapse</b> активирован. Отправьте сообщение, и я отвечу через OpenAI.")
        return {"ok": True}

    # Вызов OpenAI и ответ пользователю
    reply = call_openai_chat(text, system_prompt="You are a helpful assistant. Answer concisely in Russian when prompted in Russian.")
    send_telegram_message(chat_id, reply)
    return {"ok": True}
