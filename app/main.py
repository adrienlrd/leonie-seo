from dotenv import load_dotenv
from fastapi import FastAPI

load_dotenv()

from app.api.apply import router as apply_router
from app.api.audit import router as audit_router
from app.api.shops import router as shops_router
from app.oauth.router import router as oauth_router

app = FastAPI(
    title="Léonie SEO — Shopify App",
    version="0.1.0",
    description="SEO automation app for Shopify merchants",
)

app.include_router(oauth_router, prefix="/shopify", tags=["oauth"])
app.include_router(shops_router)
app.include_router(audit_router)
app.include_router(apply_router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}
