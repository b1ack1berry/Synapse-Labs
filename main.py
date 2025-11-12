# main.py - Flask webhook receiver + OpenAI integration + simple access control + logging
import os
import logging
import json
import requests
from flask import Flask, request, Response
import openai
import config

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("synapse")

# Configure OpenAI
openai.api_key = config.OPENAI_API_KEY

TELEGRAM_TOKEN = config.TELEGRAM_TOKEN
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
WEBHOOK_URL = config.WEBHOOK_URL

app = Flask(__name__)

def detect_lang(text: str) -> str:
    # crude detection: presence of Cyrillic -> 'ru', else 'en'
    for ch in text:
        if '\u0400' <= ch <= '\u04FF':
            return 'ru'
    return 'en'

def build_system_prompt(lang: str) -> str:
    if lang == 'ru':
        return "Ты помощник Synapse. Отвечай кратко и вежливо на русском."
    return "You are Synapse assistant. Answer concisely and politely in English."

def call_openai_chat(user_text: str, lang: str) -> str:
    system = build_system_prompt(lang)
    try:
        resp = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user_text}
            ],
            max_tokens=800,
            temperature=0.7,
            n=1,
            timeout=30
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        logger.exception("OpenAI call failed")
        return ("Ошибка при обращении к AI." if lang=='ru' else "AI request error.") + f" ({e})"

def send_telegram_message(chat_id: int, text: str, parse_mode="HTML"):
    url = f"{TELEGRAM_API}/sendMessage"
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    try:
        r = requests.post(url, json=payload, timeout=10)
        if not r.ok:
            logger.error("sendMessage failed: %s %s", r.status_code, r.text)
        return r.ok
    except Exception as e:
        logger.exception("Failed to send message")
        return False

@app.route("/", methods=["GET"])
def index():
    return f"{config.BOT_NAME} webhook alive", 200

@app.route("/set_webhook", methods=["GET"])
def set_webhook():
    # Endpoint to (re)register webhook with Telegram
    url = f"{TELEGRAM_API}/setWebhook"
    r = requests.post(url, json={"url": WEBHOOK_URL})
    logger.info("setWebhook response: %s %s", r.status_code, r.text)
    return r.text, r.status_code

@app.route("/webhook", methods=["POST"])
def webhook():
    try:
        update = request.get_json(force=True)
        logger.info("Received update: %s", json.dumps(update, ensure_ascii=False))
        # Extract message
        message = update.get("message") or update.get("edited_message") or update.get("channel_post")
        if not message:
            # unsupported update type
            return Response("ok", status=200)

        user = message.get("from", {})
        username = user.get("username", "")
        chat_id = message["chat"]["id"]
        text = message.get("text", "") or message.get("caption", "")

        # Access control
        if username not in config.ALLOWED_USERS:
            logger.warning("Access denied for user: %s", username)
            send_telegram_message(chat_id, "Доступ запрещен." if detect_lang(text)=='ru' else "Access denied.")
            return Response("forbidden", status=200)

        # handle commands
        if text.startswith("/start"):
            lang = detect_lang(text)
            welcome = ("🌑 <b>Synapse</b> активирован. Напиши сообщение и я отвечу." if lang=='ru'
                       else "🌑 <b>Synapse</b> activated. Send a message and I'll reply.")
            send_telegram_message(chat_id, welcome)
            return Response("ok", status=200)

        # Process message: call OpenAI
        lang = detect_lang(text)
        reply = call_openai_chat(text, lang)
        send_telegram_message(chat_id, reply)
        return Response("ok", status=200)
    except Exception as e:
        logger.exception("Error handling webhook")
        return Response("error", status=500)

if __name__ == '__main__':
    # On startup, try to set webhook automatically (best-effort)
    try:
        r = requests.post(f"{TELEGRAM_API}/setWebhook", json={"url": WEBHOOK_URL}, timeout=10)
        logger.info("Auto setWebhook: %s %s", r.status_code, r.text)
    except Exception as e:
        logger.exception("Auto setWebhook failed")
    # Start Flask (Render uses gunicorn, but Flask dev server here for fallback)
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
