"""Merchant niche understanding runtime."""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from typing import Any

from app.billing.subscription_store import get_plan_for_shop
from app.db_adapter import DB_PATH, get_conn
from app.llm import get_router
from app.llm.prompts import load_prompt
from app.llm.provider import CompletionResult
from app.llm.router import LLMRouter
from app.niche.engine import run_niche_analysis
from app.observability.metrics import check_budget
from app.shop_config_store import get_shop_config, set_shop_config
from app.snapshot.scope import filter_products_by_scope

PROMPT_NAME = "niche_understanding"
HYPOTHESIS_KEY = "niche_hypothesis"
HYPOTHESIS_HISTORY_KEY = "niche_hypothesis_history"
CACHE_TTL_DAYS = 30
HISTORY_LIMIT = 5

_PLAN_BUDGETS_USD = {
    "free": 0.50,
    "pro": 15.00,
    "agency": 75.00,
}

_CONFIDENCE_VALUES = {"low", "medium", "high"}
_SIZE_VALUES = {"small", "medium", "large"}
_REGISTER_VALUES = {"casual", "professional", "technical", "playful"}


class NicheUnderstandingError(RuntimeError):
    """Raised when niche understanding cannot be generated or persisted."""


def _stable_json(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _content_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_stable_json(payload).encode("utf-8")).hexdigest()


def _confidence(value: object, default: str = "medium") -> str:
    candidate = str(value or default).strip().lower()
    return candidate if candidate in _CONFIDENCE_VALUES else default


def _size(value: object) -> str:
    candidate = str(value or "medium").strip().lower()
    return candidate if candidate in _SIZE_VALUES else "medium"


def _register(value: object) -> str:
    candidate = str(value or "professional").strip().lower()
    return candidate if candidate in _REGISTER_VALUES else "professional"


def _list(value: object) -> list:
    return value if isinstance(value, list) else []


def _dict(value: object) -> dict:
    return value if isinstance(value, dict) else {}


def _top_queries(gsc_queries: list[dict], limit: int = 20) -> list[dict[str, Any]]:
    rows = sorted(gsc_queries, key=lambda row: int(row.get("impressions") or 0), reverse=True)
    return [
        {
            "query": str(row.get("query") or ""),
            "impressions": int(row.get("impressions") or 0),
            "clicks": int(row.get("clicks") or 0),
            "position": float(row.get("position") or row.get("avg_position") or 0),
        }
        for row in rows[:limit]
        if row.get("query")
    ]


def _product_summary(products: list[dict], limit: int = 30) -> list[dict[str, Any]]:
    return [
        {
            "id": str(product.get("id") or ""),
            "title": str(product.get("title") or ""),
            "product_type": str(product.get("product_type") or product.get("productType") or ""),
            "vendor": str(product.get("vendor") or ""),
            "tags": _list(product.get("tags"))[:10],
        }
        for product in products[:limit]
    ]


def build_signal_payload(shop: str, products: list[dict], gsc_queries: list[dict]) -> dict[str, Any]:
    """Build the compact, deterministic signal bundle sent to the LLM."""
    active_products = filter_products_by_scope(products, "active")
    report = run_niche_analysis(active_products, gsc_queries, shop=shop)
    report_dict = asdict(report)
    missing_inputs: list[str] = []
    if not active_products:
        missing_inputs.append("active_shopify_products")
    if not gsc_queries:
        missing_inputs.append("gsc_queries")
    if not report.entity_summary:
        missing_inputs.append("catalog_entities")

    return {
        "shop": shop,
        "active_product_count": len(active_products),
        "total_product_count": len(products),
        "total_query_count": len(gsc_queries),
        "products": _product_summary(active_products),
        "clusters": report_dict.get("clusters", [])[:10],
        "keyword_gaps": report_dict.get("keyword_gaps", [])[:15],
        "intent_clusters": report_dict.get("intent_clusters", [])[:10],
        "entity_summary": report.entity_summary,
        "top_queries": _top_queries(gsc_queries),
        "missing_inputs": missing_inputs,
    }


def _extract_json_object(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    try:
        parsed = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise NicheUnderstandingError("LLM response does not contain a JSON object") from None
        try:
            parsed = json.loads(stripped[start : end + 1])
        except json.JSONDecodeError as exc:
            raise NicheUnderstandingError(f"Invalid niche understanding JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise NicheUnderstandingError("LLM response must be a JSON object")
    return parsed


def _normalize_hypothesis(payload: dict[str, Any]) -> dict[str, Any]:
    shop_summary = _dict(payload.get("shop_summary"))
    brand_voice = _dict(payload.get("brand_voice"))

    normalized: dict[str, Any] = {
        "schema_version": str(payload.get("schema_version") or "niche_hypothesis.v1"),
        "status": str(payload.get("status") or "needs_review"),
        "shop_summary": {
            "what_you_sell": str(shop_summary.get("what_you_sell") or ""),
            "primary_niche": str(shop_summary.get("primary_niche") or ""),
            "sub_niches": [str(item) for item in _list(shop_summary.get("sub_niches"))],
            "languages_detected": [
                str(item) for item in _list(shop_summary.get("languages_detected"))
            ],
            "markets_detected": [str(item) for item in _list(shop_summary.get("markets_detected"))],
        },
        "customer_segments": [
            {
                "id": str(item.get("id") or f"segment_{idx + 1}"),
                "label": str(item.get("label") or ""),
                "description": str(item.get("description") or ""),
                "size_estimate": _size(item.get("size_estimate")),
                "confidence": _confidence(item.get("confidence")),
            }
            for idx, item in enumerate(_list(payload.get("customer_segments")))
            if isinstance(item, dict)
        ][:4],
        "buying_motivations": [
            {
                "segment_id": str(item.get("segment_id") or ""),
                "motivation": str(item.get("motivation") or ""),
                "evidence": [str(evidence) for evidence in _list(item.get("evidence"))],
                "confidence": _confidence(item.get("confidence")),
            }
            for item in _list(payload.get("buying_motivations"))
            if isinstance(item, dict)
        ],
        "objections": [
            {
                "objection": str(item.get("objection") or ""),
                "confidence": _confidence(item.get("confidence")),
            }
            for item in _list(payload.get("objections"))
            if isinstance(item, dict)
        ],
        "priority_products": [
            {
                "product_id": str(item.get("product_id") or ""),
                "reason": str(item.get("reason") or ""),
                "confidence": _confidence(item.get("confidence")),
            }
            for item in _list(payload.get("priority_products"))
            if isinstance(item, dict)
        ],
        "marketing_angles": [
            {
                "angle": str(item.get("angle") or ""),
                "for_segment_id": str(item.get("for_segment_id") or ""),
                "confidence": _confidence(item.get("confidence")),
            }
            for item in _list(payload.get("marketing_angles"))
            if isinstance(item, dict)
        ],
        "conversational_intents": [
            {
                "intent": str(item.get("intent") or ""),
                "example_queries": [str(query) for query in _list(item.get("example_queries"))],
                "confidence": _confidence(item.get("confidence")),
            }
            for item in _list(payload.get("conversational_intents"))
            if isinstance(item, dict)
        ],
        "probable_competitors": [
            {
                "name": str(item.get("name") or ""),
                "domain": item.get("domain") if item.get("domain") is not None else None,
                "confidence": _confidence(item.get("confidence")),
            }
            for item in _list(payload.get("probable_competitors"))
            if isinstance(item, dict)
        ],
        "brand_voice": {
            "tone": str(brand_voice.get("tone") or ""),
            "register": _register(brand_voice.get("register")),
            "do_say": [str(item) for item in _list(brand_voice.get("do_say"))],
            "do_not_say": [str(item) for item in _list(brand_voice.get("do_not_say"))],
            "confidence": _confidence(brand_voice.get("confidence")),
        },
        "forbidden_promises": [
            {
                "promise": str(item.get("promise") or ""),
                "reason": str(item.get("reason") or "unverifiable"),
            }
            for item in _list(payload.get("forbidden_promises"))
            if isinstance(item, dict)
        ],
        "global_confidence": _confidence(payload.get("global_confidence")),
        "missing_inputs": [str(item) for item in _list(payload.get("missing_inputs"))],
    }
    return normalized


def _fallback_hypothesis(signal_payload: dict[str, Any]) -> dict[str, Any]:
    clusters = _list(signal_payload.get("clusters"))
    top_cluster = _dict(clusters[0]) if clusters else {}
    top_queries = _list(signal_payload.get("top_queries"))
    primary_niche = str(top_cluster.get("name") or "Boutique e-commerce")
    segment_id = "main_customers"
    return _normalize_hypothesis(
        {
            "shop_summary": {
                "what_you_sell": f"Vous vendez principalement des produits autour de {primary_niche}.",
                "primary_niche": primary_niche,
                "sub_niches": [str(cluster.get("name")) for cluster in clusters[:3] if cluster.get("name")],
                "languages_detected": ["fr"],
                "markets_detected": ["FR"],
            },
            "customer_segments": [
                {
                    "id": segment_id,
                    "label": "Clients principaux",
                    "description": "Clients intéressés par les produits les plus visibles du catalogue.",
                    "size_estimate": "medium",
                    "confidence": "low" if signal_payload.get("missing_inputs") else "medium",
                }
            ],
            "buying_motivations": [
                {
                    "segment_id": segment_id,
                    "motivation": str(query.get("query") or primary_niche),
                    "evidence": ["from_gsc_query"],
                    "confidence": "medium",
                }
                for query in top_queries[:3]
            ],
            "objections": [],
            "priority_products": [
                {
                    "product_id": str(product_id),
                    "reason": f"Produit représentatif du cluster {primary_niche}.",
                    "confidence": "medium",
                }
                for product_id in _list(top_cluster.get("product_ids"))[:3]
            ],
            "marketing_angles": [
                {
                    "angle": f"Clarifier l'usage et les bénéfices liés à {primary_niche}.",
                    "for_segment_id": segment_id,
                    "confidence": "medium",
                }
            ],
            "conversational_intents": [
                {
                    "intent": str(intent.get("name") or intent.get("intent") or ""),
                    "example_queries": [str(item) for item in _list(intent.get("top_keywords"))[:3]],
                    "confidence": "medium",
                }
                for intent in _list(signal_payload.get("intent_clusters"))[:4]
                if isinstance(intent, dict)
            ],
            "probable_competitors": [],
            "brand_voice": {
                "tone": "clair, utile, rassurant",
                "register": "professional",
                "do_say": ["Mettre en avant les faits confirmés du catalogue."],
                "do_not_say": ["Ne pas inventer de certifications ou garanties."],
                "confidence": "medium",
            },
            "forbidden_promises": [
                {
                    "promise": "Garantir un résultat médical, financier ou de ranking.",
                    "reason": "unverifiable",
                }
            ],
            "global_confidence": "low" if signal_payload.get("missing_inputs") else "medium",
            "missing_inputs": _list(signal_payload.get("missing_inputs")),
        }
    )


def _cached_response(
    shop: str,
    prompt_version: str,
    content_hash: str,
    *,
    db_path=None,
) -> dict[str, Any] | None:
    path = db_path if db_path is not None else DB_PATH
    now = datetime.now(UTC).isoformat()
    with get_conn(path) as conn:
        row = conn.execute(
            """
            SELECT response_json FROM llm_cache
            WHERE shop = ?
              AND task_name = ?
              AND prompt_version = ?
              AND content_hash = ?
              AND expires_at > ?
            """,
            (shop, PROMPT_NAME, prompt_version, content_hash, now),
        ).fetchone()
    if not row:
        return None
    raw = row["response_json"] if isinstance(row, dict) else row[0]
    return json.loads(raw)


def _store_cached_response(
    shop: str,
    prompt_version: str,
    content_hash: str,
    hypothesis: dict[str, Any],
    completion: CompletionResult,
    *,
    db_path=None,
) -> None:
    path = db_path if db_path is not None else DB_PATH
    now = datetime.now(UTC)
    with get_conn(path) as conn:
        conn.execute(
            """
            INSERT INTO llm_cache
                (shop, task_name, prompt_version, content_hash, response_json,
                 tokens_in, tokens_out, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(shop, task_name, prompt_version, content_hash)
            DO UPDATE SET
                response_json = excluded.response_json,
                tokens_in = excluded.tokens_in,
                tokens_out = excluded.tokens_out,
                created_at = excluded.created_at,
                expires_at = excluded.expires_at
            """,
            (
                shop,
                PROMPT_NAME,
                prompt_version,
                content_hash,
                _stable_json(hypothesis),
                completion.tokens_in,
                completion.tokens_out,
                now.isoformat(),
                (now + timedelta(days=CACHE_TTL_DAYS)).isoformat(),
            ),
        )


def generate_niche_hypothesis(
    shop: str,
    products: list[dict],
    gsc_queries: list[dict],
    *,
    router: LLMRouter | None = None,
    force_refresh: bool = False,
    use_llm: bool = True,
    db_path=None,
) -> dict[str, Any]:
    """Generate or load a merchant niche hypothesis."""
    prompt = load_prompt(PROMPT_NAME)
    signal_payload = build_signal_payload(shop, products, gsc_queries)
    content_hash = _content_hash(signal_payload)
    plan = get_plan_for_shop(shop, db_path=db_path)
    tier = "medium" if plan == "free" else "advanced"

    if not force_refresh:
        cached = _cached_response(shop, prompt.version, content_hash, db_path=db_path)
        if cached is not None:
            cached["cache"] = {"hit": True, "content_hash": content_hash, "ttl_days": CACHE_TTL_DAYS}
            return cached

    if not use_llm:
        hypothesis = _fallback_hypothesis(signal_payload)
        completion = CompletionResult(text=_stable_json(hypothesis), provider="deterministic", model=tier)
    else:
        budget = check_budget(
            shop,
            _PLAN_BUDGETS_USD.get(plan, _PLAN_BUDGETS_USD["free"]),
            db_path=db_path,
        )
        if budget["over_budget"]:
            raise NicheUnderstandingError(str(budget["alert"] or "LLM budget exceeded"))
        llm_router = router if router is not None else get_router(shop=shop)
        completion = llm_router.complete(
            prompt.render_user(signal_json=json.dumps(signal_payload, ensure_ascii=False, indent=2)),
            system=prompt.render_system(),
            max_tokens=prompt.max_tokens,
            temperature=prompt.temperature,
        )
        hypothesis = _normalize_hypothesis(_extract_json_object(completion.text))

    hypothesis["status"] = "needs_review"
    hypothesis["generated_at"] = datetime.now(UTC).isoformat()
    hypothesis["llm_meta"] = {
        "task_name": PROMPT_NAME,
        "prompt_version": prompt.version,
        "tier": tier,
        "provider": completion.provider,
        "model": completion.model,
        "content_hash": content_hash,
    }
    hypothesis["cache"] = {"hit": False, "content_hash": content_hash, "ttl_days": CACHE_TTL_DAYS}
    _store_cached_response(shop, prompt.version, content_hash, hypothesis, completion, db_path=db_path)
    save_niche_hypothesis(shop, hypothesis)
    return hypothesis


def get_niche_hypothesis(shop: str) -> dict[str, Any] | None:
    """Return the stored niche hypothesis for a shop."""
    raw = get_shop_config(shop, HYPOTHESIS_KEY)
    return json.loads(raw) if raw else None


def get_niche_hypothesis_history(shop: str) -> list[dict[str, Any]]:
    """Return the last stored niche hypothesis versions for a shop."""
    raw = get_shop_config(shop, HYPOTHESIS_HISTORY_KEY)
    if not raw:
        return []
    parsed = json.loads(raw)
    return parsed if isinstance(parsed, list) else []


def save_niche_hypothesis(shop: str, hypothesis: dict[str, Any]) -> dict[str, Any]:
    """Persist a niche hypothesis and keep the last five previous versions."""
    normalized = _normalize_hypothesis(hypothesis)
    normalized["status"] = str(hypothesis.get("status") or normalized["status"])
    normalized["updated_at"] = datetime.now(UTC).isoformat()
    for key in ("generated_at", "llm_meta", "cache"):
        if key in hypothesis:
            normalized[key] = hypothesis[key]

    previous = get_niche_hypothesis(shop)
    history = get_niche_hypothesis_history(shop)
    if previous is not None:
        history = [previous, *history][:HISTORY_LIMIT]

    set_shop_config(shop, HYPOTHESIS_KEY, json.dumps(normalized, ensure_ascii=False))
    set_shop_config(shop, HYPOTHESIS_HISTORY_KEY, json.dumps(history, ensure_ascii=False))
    return normalized


def get_validated_niche_hypothesis(shop: str) -> dict[str, Any] | None:
    """Return the hypothesis only when the merchant validated it."""
    hypothesis = get_niche_hypothesis(shop)
    if not hypothesis or hypothesis.get("status") != "validated_by_merchant":
        return None
    return hypothesis
