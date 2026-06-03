# SEO/GEO Learning Engine

## Overview

The learning engine turns observed SEO/GEO outcomes into future prioritization signals. It is deliberately simple and explainable: each mature optimization creates an observation, observations update feature weights with a confidence-weighted moving average, and those weights slightly boost or penalize future actions.

It does not share sensitive merchant data across shops. Merchant-specific weights remain scoped to one shop. Global weights use only anonymized feature pairs such as `action_type=meta_title`, `surface=product_page`, or `keyword_source=gsc`.

## Modes

Only two modes exist:

- `semi_auto`: default and recommended. The app analyzes outcomes, learns, prepares optimizations, and asks the merchant to validate actions in one click.
- `auto_apply`: advanced. The app applies only low-risk, high-confidence changes when every safeguard passes. Medium and high-risk actions still go to merchant validation.

## Why J+14 and J+28

J+14 is an intermediate signal. It can update direction and create early caution, but its confidence score is capped at 75.

J+28 is the primary validation window. It is the main window used to decide whether an action type, surface, keyword source, or content angle is working.

J+60 can remain in history to confirm long-term effects, but it is not required for the main decision loop.

## Data Used

The engine reads:

- `geo_impact_events` before/after snapshots and metrics;
- GSC metrics when available: impressions, clicks, CTR, position;
- GA4 metrics when available: conversions and revenue;
- control metrics when present;
- market-analysis product tags, keyword sources, product category signals, and content quality;
- pending approvals and decisions made by the merchant.

When GSC or GA4 is absent, the engine falls back to available metrics and lowers confidence.

## Outcome Score

`outcome_score` ranges from -100 to +100. It combines:

- delta impressions;
- delta clicks;
- delta CTR;
- delta average position;
- delta conversions;
- delta revenue;
- delta SEO/GEO score.

If control metrics exist, the score includes relative uplift versus the control. Low volume can still produce a score, but it cannot produce high confidence.

## Confidence Score

`confidence_score` ranges from 0 to 100. It depends on:

- impression volume;
- GSC availability;
- GA4 availability;
- J+14 or J+28 maturity;
- control group availability;
- trend consistency.

Rules:

- low-volume observations are capped;
- J+14 is capped at 75;
- contradictory signals reduce confidence;
- J+28 can reach 100 when data quality is strong.

## Weight Updates

Each observation updates feature weights with:

```text
normalized_outcome = outcome_score / 100
confidence_factor = confidence_score / 100
new_weight = old_weight * 0.85 + normalized_outcome * 0.15 * confidence_factor
```

Weights are stored in:

- `learning_weights` with `scope = merchant` and `shop = <shop>`;
- `learning_weights` with `scope = global` and `shop = NULL`.

The final action score combines the existing opportunity score, SEO/GEO potential, merchant weight, anonymized global weight, confidence, risk penalty, and freshness penalty.

## Validations

In `semi_auto`, the engine creates rows in `learning_pending_approvals`. Each card shows:

- product;
- field;
- before and after;
- expected impact;
- confidence;
- risk;
- Apply, Skip, and Edit actions.

The apply action uses existing Shopify writer adapters. Every decision is written to `learning_policy_decisions`, and every applied change remains traceable through the existing SEO changes and GEO ledger flow.

## Auto-Apply

`auto_apply` requires:

- learning enabled;
- mode set to `auto_apply`;
- Pro or Agency plan;
- confidence at or above `min_confidence_to_auto_apply`;
- low risk;
- supported writer;
- confirmed live write;
- no locked merchant tag contradiction;
- per-cycle limit respected.

Allowed fields are:

- `meta_title`;
- `meta_description`;
- `product_description` when quality is high enough;
- `schema_facts` only when a safe writer exists.

Blog, FAQ storefront content, complex JSON-LD, `llms.txt`, `llms-full.txt`, `agents.md`, alt text, theme edits, and sensitive claims remain in validation unless a safe writer and explicit merchant authorization exist.

## Render Cron

Render Cron can call:

```bash
curl -X POST "$PYTHON_BACKEND_URL/api/internal/learning/run" \
  -H "X-Internal-Secret: $INTERNAL_API_SECRET" \
  -H "Content-Type: application/json"
```

The endpoint is fail-open for the app: learning errors are recorded in `learning_runs.errors_json` and do not prevent the main API from serving existing routes.

The job queue also exposes `learning_cycle` for worker-based execution.

## Local Test

Run:

```bash
ruff check app/learning app/api/learning.py tests/test_learning
ruff format app/learning app/api/learning.py tests/test_learning
pytest tests/test_learning tests/test_geo/test_validation_timeline.py tests/test_geo/test_retention_milestones.py
```

## Limits

The engine learns from observed correlations, not guaranteed causality. It avoids strong conclusions from sparse data, keeps medium and high-risk changes in validation, and remains explainable through stored decisions, weights, observations, and runs.
