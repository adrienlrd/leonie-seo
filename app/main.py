from fastapi import FastAPI

from app.oauth.router import router as oauth_router

app = FastAPI(
    title="Léonie SEO — Shopify App",
    version="0.1.0",
    description="SEO automation app for Shopify merchants",
)

app.include_router(oauth_router, prefix="/shopify", tags=["oauth"])


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
