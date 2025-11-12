import os
import logging
import requests
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()  # loads .env if present

# Configurable environment variables
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-3.5-turbo")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", 512))  # Allow setting max_tokens via .env
TIMEOUT = int(os.getenv("TIMEOUT", 30))  # Timeout in seconds

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("Required environment variables TELEGRAM_TOKEN and OPENAI_API_KEY are missing. See .env.example")

app = FastAPI(title="Synapse Telegram Webhook (FastAPI)")

# Model for Telegram Updates
class UpdateModel(BaseModel):
    update_id: int | None = None
    message: dict | None = None
    edited_message: dict | None = None

# Helper function for OpenAI API
def call_openai_chat(prompt: str, system_prompt: str | None = None) -> str:
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
        logging.exception("OpenAI request failed with error: %s", str(e))
        return "Извините, произошла ошибка при обработке запроса в OpenAI."

# Helper function for Telegram API
def send_telegram_message(chat_id: int, text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=TIMEOUT)
        r.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        logging.exception("Failed sending message to Telegram: %s", str(e))
        return False

# FastAPI startup event
@app.on_event("startup")
def startup_event():
    if TELEGRAM_WEBHOOK_URL:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
        try:
            r = requests.post(url, json={"url": TELEGRAM_WEBHOOK_URL}, timeout=TIMEOUT)
            r.raise_for_status()
            logging.info("Set webhook response: %s", r.text)
        except Exception:
            logging.exception("Failed to set Telegram webhook")

# Health check endpoint
@app.get("/", tags=["health"])
async def root():
    return {"status": "ok", "service": "synapse-telegram-webhook"}

# Webhook for receiving messages from Telegram
@app.post("/webhook")
async def webhook(request: Request):
    try:
        payload = await request.json()
    except Exception as e:
        logging.exception("Invalid JSON in webhook request")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    update = UpdateModel(**payload)
    tg_message = update.message or update.edited_message
    if not tg_message:
        return {"ok": True, "note": "no message to handle"}

    chat = tg_message.get("chat", {})
    chat_id = chat.get("id")
    text = tg_message.get("text") or tg_message.get("caption") or ""
    if not chat_id or not text:
        return {"ok": True, "note": "no text or chat_id"}

    # Command handling
    if text.startswith("/start"):
        send_telegram_message(chat_id, "🌑 <b>Synapse</b> активирован. Отправьте сообщение, и я отвечу через OpenAI.")
        return {"ok": True}

    # Call OpenAI and reply
    reply = call_openai_chat(text, system_prompt="You are a helpful assistant. Answer concisely in Russian when prompted in Russian.")
    send_telegram_message(chat_id, reply)
    return {"ok": True}
