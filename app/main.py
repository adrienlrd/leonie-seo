"""FastAPI app entry point — Léonie SEO public API."""

import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

# load_dotenv must run before any module that reads env vars at import time
load_dotenv()

from app.api.apply import router as apply_router  # noqa: E402
from app.api.audit import router as audit_router  # noqa: E402
from app.api.shops import router as shops_router  # noqa: E402
from app.api.suggestions import router as suggestions_router  # noqa: E402
from app.db import init_db  # noqa: E402
from app.oauth.router import router as oauth_router  # noqa: E402
from app.oauth.webhooks import router as webhooks_router  # noqa: E402

# Initialise every SQLite table once, fail fast if the data dir is unwritable.
init_db()

# Resolve required env vars at startup so a misconfigured deploy crashes early
# rather than 500-ing on the first /shopify/install request.
_REQUIRED_ENV = ("SHOPIFY_CLIENT_ID", "SHOPIFY_CLIENT_SECRET", "SHOPIFY_SCOPES", "APP_URL")


def _missing_required_env() -> list[str]:
    return [k for k in _REQUIRED_ENV if not os.getenv(k)]


app = FastAPI(
    title="Léonie SEO — Shopify App",
    version="0.1.0",
    description="SEO automation app for Shopify merchants",
)

# CORS — origins controlled via env var; comma-separated.
_cors_origins = [
    o.strip()
    for o in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://localhost:4173").split(
        ","
    )
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(oauth_router, prefix="/shopify", tags=["oauth"])
app.include_router(webhooks_router, prefix="/shopify/webhooks", tags=["webhooks"])
app.include_router(shops_router)
app.include_router(audit_router)
app.include_router(apply_router)
app.include_router(suggestions_router)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "missing_env": _missing_required_env(),
    }


# Serve built React frontend (production) — registered last so API routes win.
_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:
        return FileResponse(str(_DIST / "index.html"))
