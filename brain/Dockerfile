FROM python:3.11-slim

# Dependencies of the brain import closure (see test/test_docker.py, which
# imports brain.app in a copy of this image layout):
#   fastapi/uvicorn - the service itself
#   anthropic       - default provider in brain/orchestrator.py
#   requests        - brain/tools.py browse call
#   pandas + rich   - pulled in by agent.ollama.tools / agent runtime
#   python-multipart - FastAPI form support
# Pinned so image rebuilds cannot silently resolve new versions. These pins
# are the versions the test suite verifies (see CI workflow); every pin
# supports python 3.11 per PyPI requires-python metadata.
RUN pip install --no-cache-dir \
    fastapi==0.141.1 uvicorn==0.52.4 anthropic==1.4.0 requests==2.34.2 \
    pandas==3.0.5 rich==15.0.0 python-multipart==0.0.32

WORKDIR /app

# brain/app.py imports File_Manager.api.routes and brain/orchestrator.py imports
# the agent package, so the image needs all three trees. docker-compose.yml
# therefore builds this file with the repository root as the build context.
COPY brain/ ./brain/
COPY File_Manager/ ./File_Manager/
COPY agent/ ./agent/

# brain and File_Manager are namespace/regular packages living under /app.
ENV PYTHONPATH=/app

VOLUME ["/data"]

# Module path is brain.app:app - the packages are copied as directories, not
# flattened into /app, because app.py does `from brain import task_store`.
CMD ["uvicorn", "brain.app:app", "--host", "0.0.0.0", "--port", "7000"]
