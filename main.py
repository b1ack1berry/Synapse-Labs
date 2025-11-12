import os
import logging
import asyncio
from typing import Dict, Any
from dotenv import load_dotenv
import httpx
from fastapi import FastAPI, Request, BackgroundTasks
from pydantic import BaseModel
import openai

# Load .env
load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")
ALLOWED_USERS = os.getenv("ALLOWED_USERS", "Synapse,AraBysh").split(",")

if not TELEGRAM_TOKEN or not OPENAI_API_KEY or not WEBHOOK_URL:
    raise SystemExit("Missing TELEGRAM_TOKEN, OPENAI_API_KEY or WEBHOOK_URL in environment.")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

# Configure OpenAI
openai.api_key = OPENAI_API_KEY

# Logging to file
LOG_FILE = "logs.txt"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler()
    ],
)

logger = logging.getLogger("synapse_bot")

app = FastAPI(title="Synapse Telegram Bot (webhook-only)")

class UpdateModel(BaseModel):
    update_id: int
    message: Dict[str, Any] | None = None
    edited_message: Dict[str, Any] | None = None
    # we only support normal messages for now

async def send_telegram(method: str, payload: dict):
    url = f"{TELEGRAM_API}/{method}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload)
        logger.info("Telegram API %s -> %s", method, resp.status_code)
        try:
            return resp.json()
        except Exception:
            return {"status_code": resp.status_code, "text": resp.text}

async def call_openai_chat(user_text: str) -> str:
    """
    Calls OpenAI ChatCompletion (gpt-3.5-turbo) and returns assistant reply.
    Simple, resilient wrapper.
    """
    system_prompt = (
        "You are Synapse — a concise, helpful, and direct assistant that replies in Russian "
        "unless the user writes in another language. Keep answers short if user asked short questions. "
        "Respect safety limits."
    )
    try:
        # Using Chat completion endpoint (works with openai Python packages 0.x and 2.x compatibility)
        # We'll attempt to use the modern API if available, otherwise fall back.
        if hasattr(openai, "ChatCompletion"):
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text},
                ],
                max_tokens=512,
                temperature=0.6,
            )
            # response object shape can vary; try common paths
            if isinstance(response, dict):
                choices = response.get("choices", [])
                if choices:
                    return choices[0].get("message", {}).get("content", "").strip()
            # fallback string
            return str(response)
        else:
            # Newer openai client (openai.OpenAI) patterns might be different; try generic
            resp = openai.chat.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_text},
                ],
                max_tokens=512,
                temperature=0.6,
            )
            # attempt to extract
            if hasattr(resp, "choices"):
                return resp.choices[0].message.content.strip()
            return str(resp)
    except Exception as e:
        logger.exception("OpenAI call failed")
        return "Ошибка при обращении к AI: " + str(e)

def is_user_allowed(msg: Dict[str, Any]) -> bool:
    if not msg:
        return False
    frm = msg.get("from") or {}
    username = frm.get("username")
    # Accept by username if provided
    if username and username in ALLOWED_USERS:
        return True
    # accept by id list if ALLOWED_USERS contains numeric ids
    try:
        ids = [int(x) for x in ALLOWED_USERS if x.strip().isdigit()]
        user_id = frm.get("id")
        if user_id and user_id in ids:
            return True
    except Exception:
        pass
    return False

async def process_message(message: Dict[str, Any]):
    chat_id = message["chat"]["id"]
    text = message.get("text") or ""
    user = message.get("from", {})
    username = user.get("username", "")
    logger.info("Received from %s (%s): %s", username, user.get("id"), text)

    if not is_user_allowed(message):
        logger.warning("Unauthorized user attempted access: %s", username or user.get("id"))
        await send_telegram("sendMessage", {"chat_id": chat_id, "text": "Доступ запрещён.", "parse_mode": "HTML"})
        return

    # send typing action
    await send_telegram("sendChatAction", {"chat_id": chat_id, "action": "typing"})
    # call OpenAI
    ai_reply = await call_openai_chat(text)
    # reply back
    await send_telegram("sendMessage", {"chat_id": chat_id, "text": ai_reply, "parse_mode": "HTML"})

@app.post("/webhook")
async def telegram_webhook(update: UpdateModel, background_tasks: BackgroundTasks):
    data = update.dict()
    message = data.get("message") or data.get("edited_message")
    if not message:
        logger.info("No message payload in update: %s", data.get("update_id"))
        return {"ok": True}
    # process in background
    background_tasks.add_task(process_message, message)
    return {"ok": True}

@app.on_event("startup")
async def startup_event():
    # set webhook to TELEGRAM webhook URL
    set_url = f"{TELEGRAM_API}/setWebhook"
    payload = {"url": f"{WEBHOOK_URL}/webhook", "allowed_updates": ["message", "edited_message"]}
    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(set_url, json=payload)
        logger.info("Set webhook response: %s", resp.text)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "10000")), log_level="info")
