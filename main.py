import os
import logging
import asyncio
from typing import Optional, Dict, Any
import httpx
from fastapi import FastAPI, Request, BackgroundTasks, Response
import openai

# Logging to console
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger('synapse_bot')

TELEGRAM_TOKEN = os.environ.get('TELEGRAM_TOKEN')
WEBHOOK_URL = os.environ.get('WEBHOOK_URL', 'https://synapse-y6kt.onrender.com/webhook')
OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')

if not TELEGRAM_TOKEN:
    logger.warning("TELEGRAM_TOKEN is not set. Telegram calls will fail until it's provided.")
if not OPENAI_API_KEY:
    logger.warning("OPENAI_API_KEY is not set. OpenAI calls will fail until it's provided.")

# Allowed usernames (Telegram 'username' field) or user ids (as strings)
ALLOWED_USERS = set(u.strip() for u in os.environ.get('ALLOWED_USERS', 'Synapse,AraBysh,bear1berry').split(','))

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}" if TELEGRAM_TOKEN else None

openai.api_key = OPENAI_API_KEY

app = FastAPI(title="Synapse Telegram Webhook (FastAPI)")

async def send_telegram_message(chat_id: int, text: str) -> None:
    """Send message to Telegram chat_id using simple HTTP request."""
    if not TELEGRAM_TOKEN:
        logger.error("Cannot send Telegram message: TELEGRAM_TOKEN missing.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            r = await client.post(url, json=payload)
            r.raise_for_status()
            logger.info(f"Sent message to {chat_id}")
        except Exception as e:
            logger.exception(f"Failed to send message to {chat_id}: {e}")

async def call_openai(prompt: str) -> str:
    """Call OpenAI chat completion (gpt-3.5-turbo by default) and return text."""
    if not OPENAI_API_KEY:
        logger.error("OpenAI API key not provided")
        return "Ошибка: OpenAI API key не задан."
    try:
        # Use Chat Completions (widely available model)
        resp = openai.ChatCompletion.create(
            model=os.environ.get('OPENAI_MODEL', 'gpt-3.5-turbo'),
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,
            temperature=0.7,
            n=1,
        )
        content = resp['choices'][0]['message']['content'].strip()
        return content
    except Exception as e:
        logger.exception("OpenAI request failed")
        return f"Ошибка при обращении к OpenAI: {e}"

@app.on_event('startup')
async def startup_event():
    logger.info('Starting Synapse FastAPI application (startup).')
    # Optionally set webhook automatically
    if TELEGRAM_TOKEN and WEBHOOK_URL:
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                set_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
                resp = await client.post(set_url, json={"url": WEBHOOK_URL})
                logger.info(f"setWebhook response: {resp.status_code} {await resp.text()}")
        except Exception as e:
            logger.exception(f"Failed to set webhook automatically: {e}")

@app.get('/')
async def health():
    return {"status": "ok", "service": "Synapse FastAPI Telegram Bot"}

@app.post('/webhook')
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    """Endpoint for Telegram to POST updates to. Handles messages and replies."""
    try:
        update = await request.json()
    except Exception as e:
        logger.exception(f"Invalid JSON: {e}")
        return Response(status_code=400, content='invalid json')

    # Basic extraction of message content (supports 'message' and 'edited_message')
    message = update.get('message') or update.get('edited_message') or {}
    if not message:
        logger.info('Update has no message payload. Ignoring.')
        return {'ok': True}

    chat = message.get('chat', {})
    from_user = message.get('from', {})

    chat_id = chat.get('id')
    username = from_user.get('username') or str(from_user.get('id'))
    text = message.get('text') or message.get('caption') or ''

    logger.info(f"Incoming message from {username} (chat_id={chat_id}): {text[:200]}")

    # Access control
    if username not in ALLOWED_USERS:
        logger.warning(f"Access denied for user {username}")
        background_tasks.add_task(send_telegram_message, chat_id, "Доступ запрещён. Обратитесь к администратору.")
        return {'ok': True}

    # Quick commands
    if text.strip().lower().startswith('/start'):
        start_text = ("🌑 <b>Synapse</b> активирован.\n"
                      "Привет — отправь мне сообщение, и я отвечу через OpenAI.\n"
                      "Доступные команды: /start, /help, /setwebhook") 
        background_tasks.add_task(send_telegram_message, chat_id, start_text)
        return {'ok': True}

    if text.strip().lower().startswith('/help'):
        help_text = ("Synapse — телеграм-бот с OpenAI.\n"
                     "Просто отправьте любой запрос — бот ответит.\n"
                     "Контакты: @Synapse") 
        background_tasks.add_task(send_telegram_message, chat_id, help_text)
        return {'ok': True}

    if text.strip().lower().startswith('/setwebhook'):
        # allow manual set of webhook via chat
        if TELEGRAM_TOKEN and WEBHOOK_URL:
            try:
                async with httpx.AsyncClient(timeout=20.0) as client:
                    set_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook"
                    resp = await client.post(set_url, json={"url": WEBHOOK_URL})
                    background_tasks.add_task(send_telegram_message, chat_id, f"setWebhook response: {resp.status_code}")
            except Exception as e:
                background_tasks.add_task(send_telegram_message, chat_id, f"setWebhook failed: {e}")
        else:
            background_tasks.add_task(send_telegram_message, chat_id, "TELEGRAM_TOKEN или WEBHOOK_URL не заданы.")
        return {'ok': True}

    # Process user text with OpenAI in background
    async def process_and_reply(chat_id: int, user_text: str):
        logger.info('Calling OpenAI...')
        reply = await call_openai(user_text)
        await send_telegram_message(chat_id, reply)

    background_tasks.add_task(process_and_reply, chat_id, text)
    return {'ok': True}

@app.post('/set_webhook')
async def set_webhook_manual(url: Optional[str] = None):
    target = url or WEBHOOK_URL
    if not TELEGRAM_TOKEN:
        return {"ok": False, "error": "TELEGRAM_TOKEN not set"}
    async with httpx.AsyncClient(timeout=20.0) as client:
        resp = await client.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/setWebhook", json={"url": target})
        return {"status_code": resp.status_code, "response": await resp.json()}
