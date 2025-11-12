Synapse Telegram bot (Webhook) - package

Files:
- main.py   : Flask app receiving Telegram webhook, using OpenAI (ChatCompletion) to reply
- config.py : embedded keys & settings (you requested tokens to be inlined)
- requirements.txt
- Dockerfile
- Procfile

How to deploy on Render:
1. Create new Web Service.
2. Set Build Command: pip install -r requirements.txt
3. Start Command: python main.py
4. Set environment variable PORT if needed (default 10000).
5. (Optional) Visit /set_webhook to register the Telegram webhook.

Security notes:
- Tokens are embedded in config.py as requested. Keep this ZIP private.
- Allowed users are limited to usernames in config.ALLOWED_USERS.
