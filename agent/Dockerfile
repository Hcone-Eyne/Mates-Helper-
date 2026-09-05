FROM python:3.11-slim

RUN pip install --no-cache-dir fastapi uvicorn playwright && \
    playwright install --with-deps chromium

WORKDIR /app
COPY server.py agent_browser.py ./

CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "9000"]
