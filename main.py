import os
import logging
import sqlite3
import time
from typing import Optional
import requests
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from dotenv import load_dotenv
from openai import OpenAI

# Load .env if present
load_dotenv()

# --- Configuration (change in .env if needed) ---
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8323894251:AAFRGQiIQm2_DQTkBACCOZOW6PgyDaFA9HU")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "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")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://synapse-y6kt.onrender.com/webhook")
ALLOWED_USERS = os.getenv("ALLOWED_USERS", "bear1berry,AraBysh").split(",")
BOT_NAME = os.getenv("BOT_NAME", "Synapse")

# --- Logging ---
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("synapse")

# --- OpenAI client ---
client = OpenAI(api_key=OPENAI_API_KEY)

# --- Database (SQLite) ---
DB_PATH = os.getenv("DB_PATH", "history.db")

def init_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    cur = conn.cursor()
    cur.execute("""CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        username TEXT,
        role TEXT,
        text TEXT,
        ts INTEGER
    )""")
    conn.commit()
    return conn

db = init_db()

def save_message(user_id: int, username: Optional[str], role: str, text: str):
    ts = int(time.time())
    cur = db.cursor()
    cur.execute("INSERT INTO messages (user_id, username, role, text, ts) VALUES (?, ?, ?, ?, ?)",
                (user_id, username, role, text, ts))
    db.commit()

# --- FastAPI app ---
app = FastAPI()

class TelegramMessage(BaseModel):
    update_id: int
    message: Optional[dict] = None

@app.get("/health")
async def health():
    return {"status": "ok", "bot": BOT_NAME}

@app.post("/webhook")
async def webhook(update: dict):
    try:
        logger.info("Received update: %s", update)
        msg = update.get("message") or update.get("edited_message")
        if not msg:
            return {"ok": True}

        user = msg.get("from", {})
        user_id = user.get("id")
        username = user.get("username", "") or user.get("first_name", "")
        text = msg.get("text", "") or ""

        # Access control
        if username not in ALLOWED_USERS:
            logger.warning("Access denied for user: %s", username)
            # Optionally, send a short reply notifying unauthorized access (commented out)
            # send_telegram(user_id, "Access denied.")
            return {"ok": True}

        # Save incoming message
        save_message(user_id, username, "user", text)

        # Prepare messages for OpenAI
        system_prompt = f"You are {BOT_NAME} — concise, helpful assistant for Telegram users."
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": text}
        ]

        # Call OpenAI Chat Completion (gpt-4o-mini or fallback)
        try:
            logger.info("Calling OpenAI for user %s", username)
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=messages,
                max_tokens=800,
                temperature=0.2
            )
            reply = resp.choices[0].message["content"]
        except Exception as e:
            logger.exception("OpenAI call failed, using fallback text.")
            reply = "Извините, произошла ошибка при обработке запроса."

        # Save assistant reply
        save_message(user_id, username, "assistant", reply)

        # Send reply back to Telegram
        send_telegram_chat_id = msg["chat"]["id"]
        send_telegram(send_telegram_chat_id, reply)

        return {"ok": True}
    except Exception as exc:
        logger.exception("Error in webhook handler: %s", exc)
        raise HTTPException(status_code=500, detail="Internal Server Error")

def send_telegram(chat_id: int, text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    try:
        r = requests.post(url, json=payload, timeout=10)
        r.raise_for_status()
        logger.info("Sent message to chat_id=%s", chat_id)
        return r.json()
    except Exception as e:
        logger.exception("Failed to send message to Telegram: %s", e)
        return None

if __name__ == "__main__":
    # For local testing only; Render will run the app via 'python main.py' as well.
    import uvicorn
    port = int(os.environ.get("PORT", 10000))
    logger.info("Starting app on port %s", port)
    uvicorn.run("main:app", host="0.0.0.0", port=port)
