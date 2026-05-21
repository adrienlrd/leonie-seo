"""FastAPI app entry point — Léonie SEO public API."""
# ruff: noqa: I001  — import order is forced by load_dotenv() runtime constraint

import asyncio
import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# load_dotenv must run before any module that reads env vars at import time
load_dotenv()

from app.api.apply import router as apply_router  # noqa: E402
from app.api.crawl import router as crawl_router  # noqa: E402
from app.api.ice import router as ice_router  # noqa: E402
from app.api.embeddings import router as embeddings_router  # noqa: E402
from app.api.impact import router as impact_router  # noqa: E402
from app.api.multilingual import router as multilingual_router  # noqa: E402
from app.api.ga4 import router as ga4_router  # noqa: E402
from app.api.geo import router as geo_router  # noqa: E402
from app.api.web_graph import router as web_graph_router  # noqa: E402
from app.api.generate import router as generate_router  # noqa: E402
from app.api.gsc import router as gsc_router  # noqa: E402
from app.api.jsonld import router as jsonld_router  # noqa: E402
from app.api.niche import router as niche_router  # noqa: E402
from app.api.pagespeed import router as pagespeed_router  # noqa: E402
from app.api.observability import router as observability_router  # noqa: E402
from app.api.privacy import router as privacy_router  # noqa: E402
from app.api.audit import router as audit_router  # noqa: E402
from app.api.opportunities import router as opportunities_router  # noqa: E402
from app.api.priorities import router as priorities_router  # noqa: E402
from app.api.content_actions import router as content_actions_router  # noqa: E402
from app.api.safe_apply import router as safe_apply_router  # noqa: E402
from app.api.longtail import router as longtail_router  # noqa: E402
from app.api.cannibalization import router as cannibalization_router  # noqa: E402
from app.api.internal_links import router as internal_links_router  # noqa: E402
from app.api.alt_text import router as alt_text_router  # noqa: E402
from app.api.descriptions import router as descriptions_router  # noqa: E402
from app.api.redirects import router as redirects_router  # noqa: E402
from app.api.rollback import router as rollback_router  # noqa: E402
from app.api.reports import router as reports_router  # noqa: E402
from app.api.semantics import router as semantics_router  # noqa: E402
from app.api.content import router as content_router  # noqa: E402
from app.api.alerts import router as alerts_router  # noqa: E402
from app.api.hreflang import router as hreflang_router  # noqa: E402
from app.api.help import router as help_router  # noqa: E402
from app.api.shops import router as shops_router  # noqa: E402
from app.api.suggestions import router as suggestions_router  # noqa: E402
from app.billing.router import (  # noqa: E402
    billing_confirm_router,
    router as billing_router,
)
from app.db import init_db  # noqa: E402
from app.jobs.router import router as jobs_router  # noqa: E402
from app.jobs.worker import JobWorker  # noqa: E402
from app.oauth.gdpr import router as gdpr_router  # noqa: E402
from app.oauth.router import router as oauth_router  # noqa: E402
from app.oauth.webhooks import router as webhooks_router  # noqa: E402

# Initialise every SQLite/Postgres table once, fail fast if unwritable.
init_db()

# Resolve required env vars at startup so a misconfigured deploy crashes early.
# INTERNAL_API_SECRET: rejects all internal calls without it (Remix dashboard fails).
# LEONIE_MASTER_KEY: required to decrypt stored Shopify/Google tokens.
_REQUIRED_ENV = (
    "SHOPIFY_CLIENT_ID",
    "SHOPIFY_CLIENT_SECRET",
    "SHOPIFY_SCOPES",
    "APP_URL",
    "INTERNAL_API_SECRET",
    "LEONIE_MASTER_KEY",
)


def _missing_required_env() -> list[str]:
    return [k for k in _REQUIRED_ENV if not os.getenv(k)]


# ── Lifespan — background job worker ─────────────────────────────────────────


@asynccontextmanager
async def lifespan(app: FastAPI):
    worker = JobWorker()
    task = asyncio.create_task(worker.run())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Léonie SEO — Shopify App",
    version="0.1.0",
    description="SEO automation app for Shopify merchants",
    lifespan=lifespan,
)

# CORS — origins controlled via env var (comma-separated).
# Defaults include both React legacy dev port and Remix dev port.
_cors_origins = [
    o.strip()
    for o in os.getenv(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:5173,http://localhost:4173,http://localhost:3000",
    ).split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=[
        "Authorization",
        "Content-Type",
        "X-Leonie-Shop",
        "X-Internal-Secret",
        "X-Shopify-Access-Token",
        "X-Shopify-Shop-Domain",
    ],
)

app.include_router(oauth_router, prefix="/shopify", tags=["oauth"])
app.include_router(webhooks_router, prefix="/shopify/webhooks", tags=["webhooks"])
app.include_router(gdpr_router, prefix="/shopify/webhooks", tags=["gdpr"])
app.include_router(billing_router)
app.include_router(billing_confirm_router)
app.include_router(privacy_router)
app.include_router(shops_router)
app.include_router(audit_router)
app.include_router(opportunities_router)
app.include_router(priorities_router)
app.include_router(content_actions_router)
app.include_router(safe_apply_router)
app.include_router(longtail_router)
app.include_router(cannibalization_router)
app.include_router(internal_links_router)
app.include_router(alt_text_router)
app.include_router(descriptions_router)
app.include_router(redirects_router)
app.include_router(rollback_router)
app.include_router(reports_router)
app.include_router(semantics_router)
app.include_router(content_router)
app.include_router(apply_router)
app.include_router(suggestions_router)
app.include_router(help_router)
app.include_router(jobs_router)
app.include_router(generate_router)
app.include_router(gsc_router)
app.include_router(pagespeed_router)
app.include_router(crawl_router)
app.include_router(ice_router)
app.include_router(niche_router)
app.include_router(observability_router)
app.include_router(jsonld_router)
app.include_router(embeddings_router)
app.include_router(impact_router)
app.include_router(multilingual_router)
app.include_router(ga4_router)
app.include_router(geo_router)
app.include_router(alerts_router)
app.include_router(hreflang_router)
app.include_router(web_graph_router)


@app.get("/health")
async def health() -> dict:
    return {
        "status": "ok",
        "missing_env": _missing_required_env(),
    }


# NOTE: frontend/ (legacy React dashboard) is decommissioned as of task 57.
# Static file serving removed — shopify-app/ (Remix) is the sole UI layer.
