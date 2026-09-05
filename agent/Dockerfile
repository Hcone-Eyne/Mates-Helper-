# this DockerFile is going to run sandbox for ai agent!

FROM python:3.11-slim
 
# iptables is needed for the egress lockdown in entrypoint.sh
RUN apt-get update && apt-get install -y --no-install-recommends iptables \
    && rm -rf /var/lib/apt/lists/*
 
# non-root user the entrypoint drops to after locking down the network
RUN useradd -m -u 1000 appuser
 
# Install Playwright's browser to a shared path, not root's home, so
# appuser (who has no access to /root) can still launch chromium.
ENV PLAYWRIGHT_BROWSERS_PATH=/opt/playwright-browsers
RUN pip install --no-cache-dir fastapi uvicorn playwright \
    && playwright install --with-deps chromium \
    && chmod -R a+rX /opt/playwright-browsers
 
WORKDIR /app
COPY server.py agent_browser.py entrypoint.sh ./
RUN chmod +x entrypoint.sh
 
# entrypoint.sh does the root-only setup (iptables) then execs uvicorn as
# appuser itself — no CMD needed, the run command lives in entrypoint.sh
ENTRYPOINT ["./entrypoint.sh"]