"""LLM pricing table and cost computation."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# Pricing per 1 million tokens in USD (as of 2025-05).
# input = prompt tokens, output = completion tokens.
_PRICING: dict[str, dict[str, float]] = {
    # OpenAI
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gpt-4o": {"input": 5.00, "output": 15.00},
    "gpt-4-turbo": {"input": 10.00, "output": 30.00},
    # Groq (free tier — billed at $0 until quota)
    "llama3-70b-8192": {"input": 0.0, "output": 0.0},
    "llama3-8b-8192": {"input": 0.0, "output": 0.0},
    "mixtral-8x7b-32768": {"input": 0.0, "output": 0.0},
    # Cloudflare Workers AI (free tier)
    "@cf/meta/llama-2-7b-chat-fp16": {"input": 0.0, "output": 0.0},
    "@cf/mistral/mistral-7b-instruct-v0.1": {"input": 0.0, "output": 0.0},
    # Gemini (Grande boutique plan, Google Search grounding). Note: this only
    # tracks token cost — the separate Google Search grounding fee (5,000
    # free grounded prompts/month, then $14/1,000) is not token-based and has
    # no tracking mechanism here; see docs/AI_HANDOFF.md.
    "gemini-3.1-flash-lite": {"input": 0.25, "output": 1.50},
}

_UNKNOWN_PRICING: dict[str, float] = {"input": 0.0, "output": 0.0}


def compute_cost(model: str, tokens_in: int, tokens_out: int) -> float:
    """Return estimated cost in USD for a single LLM call.

    Args:
        model: Model identifier (e.g. "gpt-4o-mini").
        tokens_in: Prompt token count.
        tokens_out: Completion token count.

    Returns:
        Cost in USD, rounded to 8 decimal places.
        Returns 0.0 for unknown models (no billing data available).
    """
    pricing = _PRICING.get(model)
    if pricing is None:
        logger.warning("Unknown LLM pricing model %r; cost recorded as 0.0", model)
        pricing = _UNKNOWN_PRICING
    cost = (tokens_in * pricing["input"] + tokens_out * pricing["output"]) / 1_000_000
    return round(cost, 8)


def known_models() -> list[str]:
    """Return the list of models with known pricing."""
    return list(_PRICING.keys())
