"""Google Search Console integration."""

from app.gsc.client import GSC_SCOPES, fetch_and_store_gsc_performance

__all__ = ["GSC_SCOPES", "fetch_and_store_gsc_performance"]
