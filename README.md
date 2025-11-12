# Synapse — Telegram AI bot (Render-ready)

## What is inside
- `main.py` — bot + Flask health endpoint
- `Dockerfile` — build image for Render or any Docker host
- `requirements.txt` — Python deps
- `.env.example` — example environment variables

## How to deploy on Render (beginner-friendly)
1. Create a GitHub repo and push these files (or upload via Render's "Deploy from Dockerfile" option).
2. Go to https://dashboard.render.com and create a new **Web Service**.
   - Connect your GitHub repo (or choose Docker image option).
   - Set the Build Command: `pip install -r requirements.txt` (Render will also use Dockerfile if present).
   - Set the Start Command: `python main.py`
3. In Render service settings → Environment, add **Environment Variables**:
   - `TELEGRAM_TOKEN` — your Telegram bot token
   - `GEMINI_API_KEY` — your Google/Gemini API key
   - `OWNER_USERNAME` — your Telegram username (e.g. bear1berry)
   - (optional) `GEMINI_MODEL` — model name (default: gemini-1.5-flash)
4. Deploy. Render will build and run the service. The bot uses long-polling and will run from inside the container.
5. Check logs on Render to confirm polling started and no Gemini model errors appear.

## Notes & troubleshooting
- Prefer setting API keys in Render environment variables rather than committing `.env` with secrets.
- If Gemini model returns NotFound errors, try changing `GEMINI_MODEL` to another available model or consult Google Generative AI docs.
- Render provides automatic restarts on failures; check logs for exceptions.

## Local testing (optional)
1. Copy `.env.example` to `.env` and fill tokens.
2. Create virtualenv and install requirements.
3. Run `python main.py` and watch console logs.

---
If you want, I can push this ZIP to your repo, or prepare a ready GitHub repo and connect Render for you.
