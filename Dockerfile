FROM node:24-bookworm-slim AS node-runtime
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --ignore-scripts --omit=dev --no-audit --no-fund

FROM python:3.11-slim-bookworm
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONUTF8=1 PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
COPY --from=node-runtime /usr/local/bin/node /usr/local/bin/node
COPY --from=node-runtime /app/node_modules ./node_modules
COPY requirements-lock.txt ./
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libatomic1 \
    && pip install --no-cache-dir -r requirements-lock.txt \
    && python -m playwright install --with-deps chromium \
    && rm -rf /var/lib/apt/lists/*
COPY . .
RUN useradd --create-home --uid 10001 downloader \
    && mkdir -p /app/download_files /app/log \
    && chown -R downloader:downloader /app /ms-playwright
USER downloader
ENTRYPOINT ["python", "-m", "spider.downloader"]
