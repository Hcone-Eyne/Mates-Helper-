FROM python:3.11-slim

# NOTE: mitmproxy is deliberately left unpinned here. The verified
# mitmproxy 12.x line requires python >= 3.12, but this image is 3.11-slim,
# so pinning the known-good version would break the build. Revisit after
# moving this image to python 3.12+.
RUN pip install --no-cache-dir mitmproxy

RUN mkdir -p /logs

WORKDIR /app
COPY logger.py .

CMD ["mitmdump", "-s", "/app/logger.py", "--listen-port", "8080"]
