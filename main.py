import os
import logging
import requests
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from typing import Optional
from dotenv import load_dotenv

load_dotenv()  # Загружаем переменные окружения

# Конфигурационные переменные
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", 512))
TIMEOUT = int(os.getenv("TIMEOUT", 30))

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("Необходимые переменные окружения TELEGRAM_TOKEN и OPENAI_API_KEY отсутствуют.")

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
        logging.exception("Не удалось отправить сооб
