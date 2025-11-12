FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY . /app
# expose port used by Render
ENV PORT 10000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000"]