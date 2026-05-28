"""Deterministic business profile context metadata for downstream analyses."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

BusinessProfileContextStatus = Literal["current", "stale", "unknown", "missing_profile"]

BUSINESS_PROFILE_CONTEXT_FIELDS: tuple[str, ...] = (
    "brand_name",
    "niche_summary",
    "brand_voice",
    "target_personas",
    "content_style",
    "key_themes",
    "competitor_domains",
    "competitor_insights",
    "content_gaps",
    "internal_link_priorities",
)


def _canonicalize(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, list):
        return [_canonicalize(item) for item in value if _has_content(item)]
    if isinstance(value, dict):
        return {
            str(key): _canonicalize(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
            if _has_content(item)
        }
    if value is None:
        return None
    return value


def _has_content(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(_has_content(item) for item in value)
    if isinstance(value, dict):
        return any(_has_content(item) for item in value.values())
    return True


def build_business_profile_context_payload(profile: dict[str, Any] | None) -> dict[str, Any]:
    """Build the stable subset of a business profile used by product analysis.

    Args:
        profile: Persisted business profile data.

    Returns:
        Canonical business fields that should influence downstream product analysis.
    """
    if not isinstance(profile, dict):
        return {}

    payload: dict[str, Any] = {}
    for field in BUSINESS_PROFILE_CONTEXT_FIELDS:
        value = profile.get(field)
        if _has_content(value):
            payload[field] = _canonicalize(value)
    return payload


def compute_business_profile_context_hash(profile: dict[str, Any] | None) -> str | None:
    """Return a deterministic hash for the analysis-relevant profile context."""
    payload = build_business_profile_context_payload(profile)
    if not payload:
        return None
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_business_profile_context_meta(profile: dict[str, Any] | None) -> dict[str, Any]:
    """Build compact metadata stored with a product market analysis."""
    payload = build_business_profile_context_payload(profile)
    digest = compute_business_profile_context_hash(profile)
    brand_name = profile.get("brand_name") if isinstance(profile, dict) else None
    generated_at = profile.get("generated_at") if isinstance(profile, dict) else None
    return {
        "hash": digest,
        "status": "available" if digest else "missing",
        "field_names": sorted(payload.keys()),
        "brand_name": brand_name.strip() if isinstance(brand_name, str) else None,
        "generated_at": generated_at if isinstance(generated_at, str) else None,
    }


def resolve_business_profile_context_status(
    stored_hash: str | None,
    current_profile: dict[str, Any] | None,
) -> BusinessProfileContextStatus:
    """Compare a stored profile hash with the current profile context."""
    current_hash = compute_business_profile_context_hash(current_profile)
    if current_hash is None:
        return "missing_profile"
    if not stored_hash:
        return "unknown"
    if stored_hash == current_hash:
        return "current"
    return "stale"
