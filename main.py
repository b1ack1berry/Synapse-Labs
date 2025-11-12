import os
import logging
import requests
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv

load_dotenv()  # loads .env if present

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL")  # e.g. https://your-app.onrender.com/webhook
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("Required environment variables TELEGRAM_TOKEN and OPENAI_API_KEY are missing. See .env.example")

app = FastAPI(title="Synapse Telegram Webhook (FastAPI)")


class UpdateModel(BaseModel):
    update_id: int | None = None
    message: dict | None = None
    edited_message: dict | None = None


def call_openai_chat(prompt: str, system_prompt: str | None = None) -> str:
    """
    Call OpenAI Chat Completions (HTTP) — stable approach that avoids breaking library API differences.
    Returns assistant text (str).
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
        "model": "gpt-3.5-turbo",
        "messages": messages,
        "max_tokens": 512,
        "temperature": 0.7,
    }

    try:
        r = requests.post(url, headers=headers, json=payload, timeout=30)
        r.raise_for_status()
        data = r.json()
        # try to extract assistant reply robustly
        content = data["choices"][0]["message"]["content"]
        return content.strip()
    except Exception as e:
        logging.exception("OpenAI request failed")
        return "Извините, произошла ошибка при обработке запроса в OpenAI."


def send_telegram_message(chat_id: int, text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        return True
    except Exception as e:
        logging.exception("Failed sending message to Telegram")
        return False


@app.on_event("startup")
def startup_event():
    # set webhook if TELEGRAM_WEBHOOK_URL provided
    if TELEGRAM_WEBHOOK_URL:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
        try:
            r = requests.post(url, json={"url": TELEGRAM_WEBHOOK_URL}, timeout=10)
            r.raise_for_status()
            logging.info("Set webhook response: %s", r.text)
        except Exception:
            logging.exception("Failed to set Telegram webhook")


@app.get("/", tags=["health"])
async def root():
    return {"status": "ok", "service": "synapse-telegram-webhook"}


@app.post("/webhook")
async def webhook(request: Request):
    """Receives Telegram update (webhook). Handles new messages and edited messages.
       Implementation purposely avoids using python-telegram-bot and parses JSON directly
       to keep requirements minimal and compatibility high.
    """
    try:
        payload = await request.json()
    except Exception as e:
        logging.exception("Invalid JSON in webhook request")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Basic authentication/validation could be added here (IP check / secret token) if desired.

    update = UpdateModel(**payload)
    tg_message = update.message or update.edited_message
    if not tg_message:
        # nothing to do (could be callback_query, etc.)
        return {"ok": True, "note": "no message to handle"}

    chat = tg_message.get("chat", {})
    chat_id = chat.get("id")
    text = tg_message.get("text") or tg_message.get("caption") or ""
    if not chat_id or not text:
        return {"ok": True, "note": "no text or chat_id"}

    # Simple command handling
    if text.startswith("/start"):
        send_telegram_message(chat_id, "🌑 <b>Synapse</b> активирован. Отправьте сообщение, и я отвечу через OpenAI.")
        return {"ok": True}

    # Call OpenAI and reply
    reply = call_openai_chat(text, system_prompt="You are a helpful assistant. Answer concisely in Russian when prompted in Russian.")
    send_telegram_message(chat_id, reply)
    return {"ok": True}