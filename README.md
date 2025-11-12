Synapse Telegram bot (FastAPI)
-----------------------------
What's inside:
- main.py           # FastAPI webhook handler (Telegram -> OpenAI -> Telegram)
- requirements.txt  # pinned dependencies
- .env              # environment with embedded tokens (KEEP SECRET)
- Procfile          # for Render: use web: uvicorn main:app --host 0.0.0.0 --port $PORT

How to run locally:
1. Create a virtualenv: python -m venv venv
2. Activate it and install requirements: pip install -r requirements.txt
3. Make sure .env has TELEGRAM_TOKEN and OPENAI_API_KEY
4. Run: uvicorn main:app --host 0.0.0.0 --port 10000

Notes:
- The app sets the Telegram webhook to the WEBHOOK_URL on startup.
- You asked for no file logging; this variant doesn't write logs to disk.
- Keep the .env file secret (it contains API keys).
