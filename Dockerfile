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

# Runtime mounts (history.db, raw exports, custom tenants, generated reports)
VOLUME ["/app/data", "/app/reports", "/app/config/tenants"]

# Two run modes — defaults to CLI for backward compatibility:
#   docker run leonie-seo audit crawl     → single-tenant CLI
#   docker run -p 8000:8000 --entrypoint uvicorn leonie-seo app.main:app --host 0.0.0.0 --port 8000  → web app
ENTRYPOINT ["leonie-seo"]
CMD ["--help"]

EXPOSE 8000
