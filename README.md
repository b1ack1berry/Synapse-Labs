# Synapse Telegram Bot (FastAPI, webhook)

Included:
- main.py — FastAPI app handling Telegram webhook and proxying to OpenAI.
- requirements.txt — Python dependencies.
- .env.example — copy to `.env` and fill your secrets.
- logs.txt — runtime log (created/updated by the app).

Quick start (local / Render):
1. Copy `.env.example` to `.env` and set TELEGRAM_TOKEN, OPENAI_API_KEY, WEBHOOK_URL.
2. Install dependencies:
   ```
   pip install -r requirements.txt
   ```
3. Run:
   ```
   python main.py
   ```
4. The app will call Telegram's `setWebhook` on startup to `WEBHOOK_URL/webhook`.

Notes:
- The bot accepts messages only from usernames listed in ALLOWED_USERS.
- All logs are appended to `logs.txt`.
- This is a webhook-only bot (no polling).
