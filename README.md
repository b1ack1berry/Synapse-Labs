# Synapse Telegram Bot (FastAPI webhook)

This package contains a secure, minimal Telegram bot using FastAPI and OpenAI (chat).

## Setup
1. Copy `.env.example` to `.env` and fill your `TELEGRAM_TOKEN` and `OPENAI_API_KEY`.
2. (Optional) Set WEBHOOK_URL to your public endpoint, e.g. `https://synapse-y6kt.onrender.com/webhook`.
3. Run locally:
   ```bash
   pip install -r requirements.txt
   uvicorn main:app --host 0.0.0.0 --port 10000
   ```
4. Deploy to Render or Docker — a Dockerfile is included.

## Security notes
- Tokens are read from environment variables. Do **not** commit `.env` with real keys.
- ALLOWED_USERS whitelist accepts Telegram usernames (comma separated). If empty, all users allowed.
- Logs are written to `logs/bot.log` and `logs/dialogs.log`.

## Webhook
The app will attempt to set the Telegram webhook at startup using WEBHOOK_URL from the environment.
