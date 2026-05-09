# ── Frontend build stage ──────────────────────────────────────────────
FROM node:20-slim AS frontend-build
WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ── Python runtime stage ──────────────────────────────────────────────
FROM python:3.11-slim
WORKDIR /app

# Install package in editable mode (cached layer)
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -e ".[dev]"

# Copy backend source + config
COPY scripts/ scripts/
COPY app/ app/
COPY config/ config/

# Pull the built React assets in
COPY --from=frontend-build /frontend/dist /app/frontend/dist

# Runtime mounts (history.db, raw exports, custom tenants, generated reports)
VOLUME ["/app/data", "/app/reports", "/app/config/tenants"]

# Two run modes — defaults to CLI for backward compatibility:
#   docker run leonie-seo audit crawl     → single-tenant CLI
#   docker run -p 8000:8000 --entrypoint uvicorn leonie-seo app.main:app --host 0.0.0.0 --port 8000  → web app
ENTRYPOINT ["leonie-seo"]
CMD ["--help"]

EXPOSE 8000
