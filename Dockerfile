FROM python:3.11-slim

WORKDIR /app

# Install package in editable mode
COPY pyproject.toml requirements.txt ./
RUN pip install --no-cache-dir -e ".[dev]"

# Copy source after deps so layer is cached
COPY scripts/ scripts/
COPY config/ config/

# Runtime data lives outside the image
VOLUME ["/app/data", "/app/reports", "/app/config/tenants"]

# Default: print help
ENTRYPOINT ["leonie-seo"]
CMD ["--help"]
