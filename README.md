# Synapse FastAPI Telegram Webhook Bot

This package contains a FastAPI-based Telegram webhook bot that relays incoming messages to OpenAI Chat Completions
and returns answers back to the user. It is pre-configured to restrict access to a small set of Telegram usernames,
log to the console, and set webhook automatically on startup.

## Files
- main.py — FastAPI application
- requirements.txt — Python dependencies
- Dockerfile — build image and run with Uvicorn
- .env.example — example environment variables

## Deployment (Render)
1. Create a new Web Service on Render, connect your repo or upload this package.
2. Set environment variables in Render dashboard (TELEGRAM_TOKEN, OPENAI_API_KEY, WEBHOOK_URL, ALLOWED_USERS).
3. Use the Dockerfile option or the Python build command. The app listens on port 10000.

## Webhook URL
Use the webhook URL you provided: https://synapse-y6kt.onrender.com/webhook

## Notes
- This project expects environment variables for secrets — do not hardcode them.
- Logging is printed to stdout so Render will show logs.
- The OpenAI model defaults to gpt-3.5-turbo; change OPENAI_MODEL environment variable if you need another model.
