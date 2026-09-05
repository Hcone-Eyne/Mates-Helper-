FROM python:3.11-slim

RUN pip install --no-cache-dir mitmproxy

RUN mkdir -p /logs

WORKDIR /app
COPY logger.py .

CMD ["mitmdump", "-s", "/app/logger.py", "--listen-port", "8080"]
