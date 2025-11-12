# SynapseLab Bot - Ready ZIP
Files included:
- main.py (bot code, tokens embedded)
- requirements.txt
- Procfile (for Render / Heroku)
- README.md

Instructions:
1. Upload the repository to Render / Railway / Koyeb.
2. Make sure ports and environment variables are set (if you prefer env over embedded tokens).
3. Deploy — the bot runs polling and provides an admin panel at /admin?user=bear1berry

Security note: tokens are embedded in main.py. Treat this ZIP as sensitive and rotate tokens if sharing publicly.
