# Asset Intelligence Copilot — self-contained container
#
# Runs the API + UI on port 7860 (Hugging Face Spaces convention; override
# with -p as you like). The challenge dataset is public, so it is cloned at
# build time and the SQLite store is baked into the image: cold starts serve
# data instantly with no re-ingest. Sample and test datasets are both loaded,
# exactly as the event requires.
FROM python:3.11-slim

WORKDIR /app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update \
    && apt-get install -y --no-install-recommends git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY backend/ ./backend/
COPY frontend/ ./frontend/

RUN git clone --depth 1 https://github.com/FlytBaseAILabs/flytbase-ahc-swe-asset-intelligence-dataset.git /data/dataset

ENV PYTHONPATH=/app/backend \
    COPILOT_DB=/data/copilot.db

# Bake the merged dataset into the image at build time
RUN python -c "from app import config, db; config.DB_PATH='/data/copilot.db'; db.ingest(data_dirs=['/data/dataset/sample-data', '/data/dataset/test-data/dataset'])"

EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
