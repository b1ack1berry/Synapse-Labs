# Synapse Telegram Bot (FastAPI)

This repository contains a ready-to-deploy Telegram bot **Synapse** built with FastAPI and OpenAI (gpt-4o-mini).

Features:
- Webhook endpoint `/webhook` for Telegram.
- Access control (allowed usernames only).
- SQLite conversation history (`history.db`).
- Logging enabled.
- Example `.env` included.

Deployment:
1. Build Docker image and deploy to Render (or any container host).
2. Configure webhook in Telegram to point at: `https://synapse-y6kt.onrender.com/webhook`
3. Ensure environment variables are set (or use the provided `.env`).

Files:
- `main.py` — main FastAPI app
- `requirements.txt` — dependencies
- `Dockerfile` — container instructions
- `.env` — example environment variables (contains embedded tokens as requested)
- `history.db` — created at runtime (not included here)

