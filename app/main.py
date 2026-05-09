import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

load_dotenv()

from app.api.apply import router as apply_router
from app.oauth.token_store import init_token_table

init_token_table()
from app.api.audit import router as audit_router
from app.api.shops import router as shops_router
from app.oauth.router import router as oauth_router

app = FastAPI(
    title="Léonie SEO — Shopify App",
    version="0.1.0",
    description="SEO automation app for Shopify merchants",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(oauth_router, prefix="/shopify", tags=["oauth"])
app.include_router(shops_router)
app.include_router(audit_router)
app.include_router(apply_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# Serve built React frontend (production) — must be registered last
_DIST = Path(__file__).parent.parent / "frontend" / "dist"
if _DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str) -> FileResponse:
        return FileResponse(str(_DIST / "index.html"))
