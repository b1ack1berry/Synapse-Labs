# Synapse Telegram Webhook (FastAPI)

This repository contains a minimal FastAPI app that accepts Telegram webhook updates at `/webhook` and forwards messages to OpenAI Chat Completions, then replies back to the user.

Files:
- `main.py` - FastAPI app (webhook handler, OpenAI + Telegram HTTP integration)
- `requirements.txt` - Python dependencies
- `.env.example` - example environment variables (do not commit secrets)
- `README.md` - this file

Deployment notes:
- Fill `.env` with `TELEGRAM_TOKEN`, `OPENAI_API_KEY`, and `TELEGRAM_WEBHOOK_URL`.
- On Render, set the build command: `pip install -r requirements.txt`
- Start command: `python main.py` (or use `uvicorn main:app --host 0.0.0.0 --port $PORT`)

Security:
- Tokens are read from environment variables. Do NOT commit real keys.
- For extra safety, consider validating Telegram requests using a secret path or IP allowlist.
