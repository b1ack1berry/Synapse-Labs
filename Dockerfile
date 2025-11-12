FROM python:3.11-slim
WORKDIR /app
# system deps for some wheels
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev build-essential && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 10000
# runtime env vars: TELEGRAM_TOKEN, OPENAI_API_KEY, WEBHOOK_URL, PORT
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]
