Synapse Telegram Bot (FastAPI webhook)
====================================

Files:
- main.py          -- FastAPI app with /webhook endpoint
- requirements.txt -- Python deps
- Dockerfile       -- optional Dockerfile
- logs/errors.log  -- runtime log file (created at runtime)

Configuration (already embedded):
- TELEGRAM token embedded in main.py
- OPENAI API key embedded in main.py
- TELEGRAM_WEBHOOK_URL set in main.py to https://synapse-y6kt.onrender.com/webhook

Notes:
- Allowed users are set to ['@bear1berry', 'AraBysh'] in main.py
- This project logs to logs/errors.log and to console.
- To run locally:
    uvicorn main:app --host 0.0.0.0 --port 10000
- To set webhook for Telegram (example):
    curl -F "url=https://synapse-y6kt.onrender.com/webhook" https://api.telegram.org/bot<YOUR_TOKEN>/setWebhook
