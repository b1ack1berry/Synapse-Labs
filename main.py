import os
import logging
import httpx
import openai
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from typing import Any, Dict

# ========== CONFIG (вшиты по просьбе) ==========
TELEGRAM_TOKEN = "8323894251:AAFRGQiIQm2_DQTkBACCOZOW6PgyDaFA9HU"
OPENAI_API_KEY = "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"
TELEGRAM_WEBHOOK_URL = "https://synapse-y6kt.onrender.com/webhook"

# Allowed users: usernames (with or without @) or numeric ids
ALLOWED_USERS = ["@bear1berry", "AraBysh"]  # only these users allowed; others rejected

# OpenAI model to use (change if needed)
OPENAI_MODEL = "gpt-3.5-turbo"

# Logging setup
LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "errors.log")
logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s - %(message)s",
                    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"),
                              logging.StreamHandler()])
logger = logging.getLogger("synapse")

# Initialize OpenAI
openai.api_key = OPENAI_API_KEY

app = FastAPI(title="Synapse Telegram Bot Webhook")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

class TelegramMessage(BaseModel):
    update_id: int
    message: Dict[str, Any] = None
    edited_message: Dict[str, Any] = None
    callback_query: Dict[str, Any] = None

def is_allowed(user: Dict[str, Any]) -> bool:
    if not user:
        return False
    username = user.get("username")
    user_id = user.get("id")
    if username and ("@" + username in ALLOWED_USERS or username in ALLOWED_USERS):
        return True
    if user_id and str(user_id) in ALLOWED_USERS:
        return True
    return False

async def send_telegram(chat_id: int, text: str, parse_mode: str = "HTML"):
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(url, json=payload)
    if r.status_code != 200:
        logger.error("Failed to send message to %s: %s %s", chat_id, r.status_code, r.text)
    return r

async def call_openai(prompt: str) -> str:
    try:
        # Use chat completion for better context handling
        response = openai.ChatCompletion.create(
            model=OPENAI_MODEL,
            messages=[{"role":"user","content": prompt}],
            max_tokens=512,
            temperature=0.7
        )
        # Extract assistant reply
        if "choices" in response and len(response.choices) > 0:
            return response.choices[0].message.get("content", "").strip()
        return "Извините, модель вернула пустой ответ."
    except Exception as e:
        logger.exception("OpenAI call failed")
        return "Ошибка при обращении к OpenAI: " + str(e)

@app.post("/webhook")
async def webhook(update: TelegramMessage):
    try:
        data = update.dict()
        message = data.get("message") or data.get("edited_message")
        if not message:
            # ignore non-message updates for now
            return {"ok": True, "note": "no message"}

        chat = message.get("chat", {})
        from_user = message.get("from", {})
        text = message.get("text", "") or message.get("caption", "") or ""

        username = from_user.get("username")
        user_id = from_user.get("id")

        logger.info("Received message from %s (%s): %s", username, user_id, text[:200])

        if not is_allowed(from_user):
            logger.info("User not allowed: %s (%s)", username, user_id)
            await send_telegram(chat.get("id"), "Доступ ограничен для этого пользователя.")
            return {"ok": False, "reason": "user_not_allowed"}

        # Simple commands
        if text.startswith("/start") or text.startswith("Привет") or text.startswith("/help"):
            welcome = ("🌑 <b>Synapse</b> активирован.\n\n"
                       "Отправь сообщение — бот ответит через OpenAI.\n"
                       "Доступ: только для авторизованных пользователей.")
            await send_telegram(chat.get("id"), welcome)
            return {"ok": True}

        # Forward to OpenAI
        prompt = f"Пользователь @{username} ({user_id}) пишет: {text}"
        ai_reply = await call_openai(prompt)
        await send_telegram(chat.get("id"), ai_reply)
        return {"ok": True}
    except Exception as e:
        logger.exception("Error handling webhook")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return {"status":"ok", "info":"Synapse Telegram Bot running. Webhook endpoint: /webhook"}
