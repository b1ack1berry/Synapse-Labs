import os
import logging
from logging.handlers import RotatingFileHandler
from fastapi import FastAPI, Request, HTTPException
import httpx
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://synapse-y6kt.onrender.com/webhook")
ALLOWED_USERS = os.getenv("ALLOWED_USERS", "bear1berry,AraBysh").split(",")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("TELEGRAM_TOKEN and OPENAI_API_KEY must be set in environment variables. See .env.example")

# Logging setup
logs_dir = Path("logs") if 'Path' in globals() else None
if logs_dir:
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
logger = logging.getLogger("synapse")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler("logs/bot.log", maxBytes=2_000_000, backupCount=5, encoding="utf-8")
fmt = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
handler.setFormatter(fmt)
logger.addHandler(handler)

# Dialogs log
dialogs_handler = RotatingFileHandler("logs/dialogs.log", maxBytes=5_000_000, backupCount=3, encoding="utf-8")
dialogs_handler.setFormatter(fmt)
dialogs_logger = logging.getLogger("dialogs")
dialogs_logger.setLevel(logging.INFO)
dialogs_logger.addHandler(dialogs_handler)

app = FastAPI(title="Synapse (Telegram webhook)", version="1.0")

# OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY)

TELEGRAM_API_BASE = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

async def send_telegram_message(chat_id: int, text: str, parse_mode: str = "HTML"):
    url = f"{TELEGRAM_API_BASE}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(url, json=payload)
        logger.info(f"Telegram sendMessage status: {r.status_code} resp={r.text}")
        return r

@app.on_event("startup")
async def startup_event():
    logger.info("Starting Synapse webhook service...")
    # Try to set webhook (idempotent)
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            r = await client.post(f"{TELEGRAM_API_BASE}/setWebhook", json={"url": WEBHOOK_URL})
            logger.info("Set webhook response: %s", r.text)
    except Exception as e:
        logger.exception("Failed to set webhook on startup: %s", e)

@app.get("/health")
async def health():
    return {"status": "ok"}

@app.post("/webhook")
async def telegram_webhook(request: Request):
    payload = await request.json()
    logger.info("Incoming update: %s", payload)
    # Basic validation
    if "message" not in payload and "edited_message" not in payload:
        logger.warning("Unsupported update received (no message).")
        return {"ok": True}

    msg = payload.get("message") or payload.get("edited_message")
    from_user = msg.get("from", {})
    username = from_user.get("username")
    chat_id = msg["chat"]["id"]
    text = msg.get("text", "")

    # Whitelist check by username (if provided)
    if username and username not in ALLOWED_USERS:
        logger.info("User %s not allowed. Denying.", username)
        await send_telegram_message(chat_id, "⛔ Доступ запрещён. Обратитесь к администратору.", "HTML")
        return {"ok": True}

    # Log dialog
    dialogs_logger.info("user=%s chat_id=%s text=%s", username or from_user.get("id"), chat_id, text)

    if not text:
        await send_telegram_message(chat_id, "Я принимаю только текстовые сообщения.", "HTML")
        return {"ok": True}

    # Construct prompt for OpenAI
    user_prompt = f"Пользователь @{username or from_user.get('id')}: {text}\nОтветь коротко, персонально, с эмодзи."
    try:
        response = openai_client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": user_prompt}],
            max_tokens=700,
        )
        # extract assistant text
        assistant_text = ""
        if getattr(response, "choices", None):
            assistant_text = response.choices[0].message["content"] if response.choices[0].message else str(response.choices[0])
        else:
            assistant_text = str(response)
        # send back to telegram
        await send_telegram_message(chat_id, assistant_text, "HTML")
        dialogs_logger.info("assistant reply: %s", assistant_text)
    except Exception as e:
        logger.exception("OpenAI request failed: %s", e)
        await send_telegram_message(chat_id, "⚠️ Ошибка при обработке запроса. Попробуйте позже.", "HTML")

    return {"ok": True}
