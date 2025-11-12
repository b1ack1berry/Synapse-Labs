import os
import asyncio
from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
from openai import OpenAI
import httpx

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://synapse-y6kt.onrender.com/webhook")

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise RuntimeError("TELEGRAM_TOKEN and OPENAI_API_KEY must be set in environment or .env file")

TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

app = FastAPI(title="Synapse Telegram Webhook (FastAPI)")


class UpdateModel(BaseModel):
    update_id: int
    message: dict | None = None
    edited_message: dict | None = None
    callback_query: dict | None = None


# Initialize OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY)


async def send_telegram_message(chat_id: int, text: str, parse_mode: str = "HTML"):
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        return r.json()


async def generate_reply(prompt: str) -> str:
    # Use OpenAI (openai-python v2) chat completions API
    # Model choice is conservative; adjust if you prefer a different one.
    resp = openai_client.chat.completions.create(
        model="gpt-4o-mini", 
        messages=[{"role":"user","content": prompt}],
        max_tokens=512,
        temperature=0.7,
    )
    # Extract assistant content safely
    try:
        return resp.choices[0].message["content"].strip()
    except Exception:
        # Fallback if structure differs
        return str(resp)


@app.post("/webhook")
async def webhook(update: UpdateModel):
    # Handle different update types; we only reply to standard messages.
    msg = update.message or update.edited_message
    if not msg:
        # ignore other update types (callback_query etc.)
        raise HTTPException(status_code=204, detail="No message to process")

    chat = msg.get("chat") or {}
    chat_id = chat.get("id")
    text = msg.get("text") or ""

    if not chat_id or text is None:
        raise HTTPException(status_code=400, detail="Invalid message payload")

    # Simple commands
    if text.strip().lower() in ("/start", "start"):
        reply = "🌑 <b>Synapse</b> активирован. Привет! Отправь мне сообщение — я отвечу."
        await send_telegram_message(chat_id, reply)
        return {"ok": True}

    # Call OpenAI to generate reply
    try:
        reply_text = await asyncio.to_thread(generate_reply, text)
    except Exception as e:
        # graceful error message to user
        await send_telegram_message(chat_id, "Ошибка обработки запроса. Попробуйте позже.")
        return {"ok": False, "error": str(e)}

    # Send reply back to Telegram
    try:
        await send_telegram_message(chat_id, reply_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send message: {e}")

    return {"ok": True}


@app.on_event("startup")
async def startup_event():
    # set webhook on startup
    async with httpx.AsyncClient(timeout=15.0) as client:
        r = await client.post(f"{TELEGRAM_API}/setWebhook", json={"url": WEBHOOK_URL})
        r.raise_for_status()
        # keep a small sleep to allow Telegram to accept it
        await asyncio.sleep(0.1)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "10000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
