"""AI Visibility status endpoint.

V1 product stance (do not relax without explicit approval — see
`docs/launch-readiness.md` §3.7 and `docs/impact-tracker.md` §16):

- AI Visibility (how ChatGPT / Perplexity / Gemini describe or cite a store) is a
  **measured signal, never a guarantee**. The app must not promise appearance in
  AI engines.
- The active measurement is intentionally **disabled in V1** and surfaced as a
  separate axis from Search Performance (§3.8). This endpoint advertises that
  honest framing; the live measurement ships later as an opt-in (``available_in``).

This endpoint is intentionally lightweight (no auth dependency, no LLM call, no
billing): it only returns the disabled status + the no-promise messaging the UI
renders.
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["ai-visibility"])

# Exact no-promise framing required by launch-readiness §3.7.
_MESSAGE_FR = (
    "La présence dans les moteurs IA (ChatGPT, Perplexity, Gemini) n'est jamais "
    "garantie ; il s'agit d'un signal mesuré, pas d'une promesse. La mesure "
    "automatique arrivera dans une prochaine version."
)
_MESSAGE_EN = (
    "Presence in AI engines (ChatGPT, Perplexity, Gemini) is never guaranteed; it "
    "is a measured signal, not a promise. Automatic measurement is coming in a "
    "future version."
)


@router.get("/shops/{shop}/ai-visibility/status")
def ai_visibility_status(shop: str) -> dict:
    """Return the AI Visibility axis status.

    V1: ``enabled = False`` with ``available_in = "v2"`` and the no-promise
    messaging. Kept separate from Search Performance (no score aggregation).
    """
    return {
        "axis": "ai_visibility",
        "enabled": False,
        "available_in": "v2",
        "guaranteed": False,
        "message_fr": _MESSAGE_FR,
        "message_en": _MESSAGE_EN,
    }
