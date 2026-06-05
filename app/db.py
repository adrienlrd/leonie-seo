"""Centralized database initialization for all app tables.

Called once at startup from app/main.py. Uses Postgres when DATABASE_URL is set
(production / Neon), SQLite otherwise (local dev / tests).
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from app.db_adapter import DB_PATH  # single canonical path, re-exported for consumers

__all__ = ["DB_PATH", "init_db"]

# ── SQLite DDL ─────────────────────────────────────────────────────────────────

_SQLITE_DDL = [
    """CREATE TABLE IF NOT EXISTS shop_tokens (
        shop         TEXT PRIMARY KEY,
        access_token TEXT NOT NULL,
        scope        TEXT,
        installed_at TEXT NOT NULL,
        updated_at   TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS google_tokens (
        shop         TEXT PRIMARY KEY,
        token_json   TEXT NOT NULL,
        scopes       TEXT,
        email        TEXT,
        created_at   TEXT NOT NULL,
        updated_at   TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS oauth_states (
        state      TEXT PRIMARY KEY,
        created_at REAL NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS seo_changes (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        shop          TEXT,
        applied_at    TEXT NOT NULL,
        resource_type TEXT NOT NULL,
        resource_id   TEXT NOT NULL,
        field         TEXT NOT NULL,
        old_value     TEXT,
        new_value     TEXT,
        status        TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS snapshots (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        shop          TEXT,
        snapshot_date TEXT NOT NULL,
        resource_type TEXT NOT NULL,
        resource_id   TEXT NOT NULL,
        data_json     TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS gdpr_requests (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        received_at TEXT NOT NULL,
        topic       TEXT NOT NULL,
        shop        TEXT NOT NULL,
        payload     TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS subscriptions (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        shop            TEXT NOT NULL UNIQUE,
        subscription_id TEXT,
        plan            TEXT NOT NULL DEFAULT 'free',
        status          TEXT NOT NULL DEFAULT 'pending',
        created_at      TEXT NOT NULL,
        updated_at      TEXT NOT NULL
    )""",
    # LLM meta suggestions (Phase 7, task 60)
    """CREATE TABLE IF NOT EXISTS meta_suggestions (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        shop                TEXT NOT NULL,
        product_id          TEXT NOT NULL,
        product_title       TEXT NOT NULL,
        generated_title     TEXT,
        generated_description TEXT,
        provider            TEXT,
        status              TEXT NOT NULL DEFAULT 'pending',
        error               TEXT,
        job_id              TEXT,
        created_at          TEXT NOT NULL DEFAULT (datetime('now'))
    )""",
    # LLM usage metrics (Phase 7, task 68)
    """CREATE TABLE IF NOT EXISTS llm_metrics (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        shop        TEXT,
        provider    TEXT NOT NULL,
        model       TEXT NOT NULL,
        tokens_in   INTEGER NOT NULL DEFAULT 0,
        tokens_out  INTEGER NOT NULL DEFAULT 0,
        cost_usd    REAL NOT NULL DEFAULT 0.0,
        latency_ms  REAL NOT NULL DEFAULT 0.0,
        error       TEXT,
        called_at   TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS llm_cache (
        shop           TEXT NOT NULL,
        task_name      TEXT NOT NULL,
        prompt_version TEXT NOT NULL,
        content_hash   TEXT NOT NULL,
        response_json  TEXT NOT NULL,
        tokens_in      INTEGER NOT NULL DEFAULT 0,
        tokens_out     INTEGER NOT NULL DEFAULT 0,
        created_at     TEXT NOT NULL,
        expires_at     TEXT NOT NULL,
        PRIMARY KEY (shop, task_name, prompt_version, content_hash)
    )""",
    # Shared keyword-data cache (volume/difficulty/SERP-PAA). Keyed by
    # data_type+location+language+keyword and intentionally NOT scoped to a shop:
    # keyword market data is identical across shops, so the cache is shared to cut
    # repeated paid-provider calls as more shops are onboarded.
    """CREATE TABLE IF NOT EXISTS keyword_data_cache (
        cache_key    TEXT PRIMARY KEY,
        data_type    TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        created_at   TEXT NOT NULL,
        expires_at   TEXT NOT NULL
    )""",
    # Semantic embeddings (Phase 8, task 70) — stored as JSON text for SQLite
    """CREATE TABLE IF NOT EXISTS product_embeddings (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        shop          TEXT NOT NULL,
        product_id    TEXT NOT NULL,
        product_title TEXT NOT NULL DEFAULT '',
        embedding     TEXT NOT NULL,
        model         TEXT NOT NULL DEFAULT 'intfloat/multilingual-e5-base',
        created_at    TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(shop, product_id)
    )""",
    """CREATE TABLE IF NOT EXISTS query_embeddings (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        shop       TEXT NOT NULL,
        query      TEXT NOT NULL,
        embedding  TEXT NOT NULL,
        model      TEXT NOT NULL DEFAULT 'intfloat/multilingual-e5-base',
        created_at TEXT NOT NULL DEFAULT (datetime('now')),
        UNIQUE(shop, query)
    )""",
    # Generic per-shop key/value config (Phase 10, task 89+)
    """CREATE TABLE IF NOT EXISTS shop_config (
        shop  TEXT NOT NULL,
        key   TEXT NOT NULL,
        value TEXT NOT NULL,
        PRIMARY KEY (shop, key)
    )""",
    # Async job queue (Phase 6, task 55)
    """CREATE TABLE IF NOT EXISTS jobs (
        id           TEXT PRIMARY KEY,
        queue        TEXT NOT NULL,
        payload      TEXT NOT NULL,
        shop         TEXT,
        status       TEXT NOT NULL DEFAULT 'pending',
        priority     INTEGER NOT NULL DEFAULT 0,
        retries      INTEGER NOT NULL DEFAULT 0,
        max_retries  INTEGER NOT NULL DEFAULT 3,
        scheduled_at TEXT NOT NULL,
        started_at   TEXT,
        completed_at TEXT,
        result       TEXT,
        created_at   TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS geo_impact_events (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        shop               TEXT NOT NULL,
        created_at         TEXT NOT NULL,
        event_type         TEXT NOT NULL,
        resource_type      TEXT NOT NULL,
        resource_id        TEXT NOT NULL,
        resource_title     TEXT NOT NULL DEFAULT '',
        action_type        TEXT NOT NULL,
        status             TEXT NOT NULL DEFAULT 'planned',
        source             TEXT NOT NULL DEFAULT 'geo',
        job_id             TEXT,
        snapshot_id        INTEGER,
        hypothesis         TEXT,
        score_before       INTEGER,
        score_after        INTEGER,
        measurement_status TEXT NOT NULL DEFAULT 'not_started',
        status_history     TEXT,
        before_snapshot    TEXT NOT NULL,
        after_snapshot     TEXT,
        metrics_before     TEXT NOT NULL,
        metrics_after      TEXT,
        estimated_impact   TEXT NOT NULL,
        observed_impact    TEXT,
        notes              TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS geo_optimization_snapshots (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        shop               TEXT NOT NULL,
        created_at         TEXT NOT NULL,
        resource_type      TEXT NOT NULL,
        resource_id        TEXT NOT NULL,
        resource_title     TEXT NOT NULL DEFAULT '',
        action_type        TEXT NOT NULL,
        source             TEXT NOT NULL DEFAULT 'geo',
        hypothesis         TEXT,
        snapshot_json      TEXT NOT NULL,
        metrics_json       TEXT NOT NULL,
        readiness_score    INTEGER NOT NULL DEFAULT 0,
        seo_score          INTEGER NOT NULL DEFAULT 0,
        content_hash       TEXT NOT NULL DEFAULT '',
        notes              TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS crawl_findings (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        shop          TEXT NOT NULL,
        created_at    TEXT NOT NULL,
        source        TEXT NOT NULL DEFAULT 'crawl_l3',
        url           TEXT NOT NULL,
        issue_type    TEXT NOT NULL,
        severity      TEXT NOT NULL,
        detail        TEXT NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}'
    )""",
    """CREATE TABLE IF NOT EXISTS competitor_crawl_cache (
        id                INTEGER PRIMARY KEY AUTOINCREMENT,
        url               TEXT NOT NULL UNIQUE,
        domain            TEXT NOT NULL,
        fetched_at        TEXT NOT NULL,
        status_code       INTEGER,
        final_url         TEXT,
        allowed_by_robots INTEGER NOT NULL DEFAULT 0,
        html_hash         TEXT NOT NULL DEFAULT '',
        features_json     TEXT NOT NULL DEFAULT '{}',
        error             TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS competitor_crawl_runs (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        shop            TEXT NOT NULL,
        created_at      TEXT NOT NULL,
        enabled         INTEGER NOT NULL DEFAULT 0,
        urls_selected   INTEGER NOT NULL DEFAULT 0,
        urls_fetched    INTEGER NOT NULL DEFAULT 0,
        urls_from_cache INTEGER NOT NULL DEFAULT 0,
        errors_count    INTEGER NOT NULL DEFAULT 0,
        summary_json    TEXT NOT NULL DEFAULT '{}'
    )""",
    # Unified content actions drafts (Phase 11.8, task 145)
    """CREATE TABLE IF NOT EXISTS content_actions (
        action_id      TEXT PRIMARY KEY,
        shop           TEXT NOT NULL,
        content_type   TEXT NOT NULL,
        resource_id    TEXT NOT NULL,
        resource_handle TEXT NOT NULL DEFAULT '',
        result_json    TEXT NOT NULL,
        status         TEXT NOT NULL DEFAULT 'draft',
        retry_count    INTEGER NOT NULL DEFAULT 0,
        created_at     TEXT NOT NULL,
        updated_at     TEXT NOT NULL
    )""",
    # Human review decisions for content actions (Phase 11.8, task 146)
    """CREATE TABLE IF NOT EXISTS content_action_decisions (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        shop            TEXT NOT NULL,
        action_id       TEXT NOT NULL,
        content_type    TEXT NOT NULL,
        decision        TEXT NOT NULL,
        decided_by      TEXT NOT NULL DEFAULT 'merchant',
        decided_at      TEXT NOT NULL,
        before_hash     TEXT,
        after_hash      TEXT,
        edit_diff       TEXT,
        rejected_reason TEXT,
        retry_index     INTEGER NOT NULL DEFAULT 0
    )""",
    # AI discovery templates (agents.md / llms.txt / llms-full.txt) publication
    # state, one row per shop. The files are written to the published theme.
    """CREATE TABLE IF NOT EXISTS llms_txt_publications (
        shop                 TEXT PRIMARY KEY,
        theme_id             TEXT,
        agents_hash          TEXT,
        llms_hash            TEXT,
        full_hash            TEXT,
        last_published_at    TEXT,
        last_webhook_tick_at TEXT,
        is_published         INTEGER NOT NULL DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS product_improvement_tags (
        shop                TEXT NOT NULL,
        product_id          TEXT NOT NULL,
        tag_id              TEXT NOT NULL,
        label               TEXT NOT NULL,
        tag_type            TEXT NOT NULL,
        status              TEXT NOT NULL DEFAULT 'neutral',
        score               INTEGER NOT NULL DEFAULT 0,
        source              TEXT NOT NULL DEFAULT 'market_analysis',
        locked_by_merchant  INTEGER NOT NULL DEFAULT 0,
        reason              TEXT,
        first_seen_at       TEXT NOT NULL,
        last_seen_at        TEXT NOT NULL,
        updated_at          TEXT NOT NULL,
        PRIMARY KEY (shop, product_id, tag_id)
    )""",
    """CREATE TABLE IF NOT EXISTS tag_performance_history (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        shop           TEXT NOT NULL,
        product_id     TEXT NOT NULL,
        tag_id         TEXT NOT NULL,
        label          TEXT NOT NULL,
        status_before  TEXT NOT NULL,
        status_after   TEXT NOT NULL,
        measurement_window TEXT NOT NULL,
        metrics_json   TEXT NOT NULL DEFAULT '{}',
        reason         TEXT NOT NULL DEFAULT '',
        decided_at     TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS continuous_improvement_agent_runs (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        shop           TEXT NOT NULL,
        created_at     TEXT NOT NULL,
        mode           TEXT NOT NULL DEFAULT 'semi_auto',
        status         TEXT NOT NULL DEFAULT 'completed',
        summary_json   TEXT NOT NULL DEFAULT '{}',
        proposals_json TEXT NOT NULL DEFAULT '[]',
        errors_json    TEXT NOT NULL DEFAULT '[]'
    )""",
    """CREATE TABLE IF NOT EXISTS learning_observations (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        shop                 TEXT NOT NULL,
        ledger_event_id      INTEGER,
        resource_type        TEXT NOT NULL,
        resource_id          TEXT NOT NULL,
        action_type          TEXT NOT NULL,
        surface              TEXT NOT NULL,
        keyword_source       TEXT NOT NULL,
        before_metrics_json  TEXT NOT NULL DEFAULT '{}',
        after_metrics_json   TEXT NOT NULL DEFAULT '{}',
        control_metrics_json TEXT NOT NULL DEFAULT '{}',
        window_days          INTEGER NOT NULL,
        window_label         TEXT NOT NULL,
        is_primary_window    INTEGER NOT NULL DEFAULT 0,
        outcome_score        REAL NOT NULL DEFAULT 0,
        confidence_score     INTEGER NOT NULL DEFAULT 0,
        metadata_json        TEXT NOT NULL DEFAULT '{}',
        created_at           TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS learning_weights (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        scope         TEXT NOT NULL,
        shop          TEXT,
        feature_key   TEXT NOT NULL,
        feature_value TEXT NOT NULL,
        weight        REAL NOT NULL DEFAULT 0,
        sample_size   INTEGER NOT NULL DEFAULT 0,
        confidence    INTEGER NOT NULL DEFAULT 0,
        updated_at    TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS learning_runs (
        id                     INTEGER PRIMARY KEY AUTOINCREMENT,
        shop                   TEXT NOT NULL,
        status                 TEXT NOT NULL,
        observations_created   INTEGER NOT NULL DEFAULT 0,
        weights_updated        INTEGER NOT NULL DEFAULT 0,
        actions_reprioritized  INTEGER NOT NULL DEFAULT 0,
        approvals_created      INTEGER NOT NULL DEFAULT 0,
        auto_applied_count     INTEGER NOT NULL DEFAULT 0,
        errors_json            TEXT NOT NULL DEFAULT '[]',
        created_at             TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS learning_policy_decisions (
        id                 INTEGER PRIMARY KEY AUTOINCREMENT,
        shop               TEXT NOT NULL,
        resource_id        TEXT NOT NULL,
        action_type        TEXT NOT NULL,
        previous_score     REAL NOT NULL DEFAULT 0,
        learning_score     REAL NOT NULL DEFAULT 0,
        final_score        REAL NOT NULL DEFAULT 0,
        mode               TEXT NOT NULL DEFAULT 'semi_auto',
        approval_required  INTEGER NOT NULL DEFAULT 1,
        risk_level         TEXT NOT NULL DEFAULT 'medium',
        merchant_decision  TEXT NOT NULL DEFAULT 'pending',
        explanation_json   TEXT NOT NULL DEFAULT '{}',
        applied_at         TEXT,
        reviewed_at        TEXT,
        created_at         TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS learning_pending_approvals (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        shop                 TEXT NOT NULL,
        resource_type        TEXT NOT NULL,
        resource_id          TEXT NOT NULL,
        action_type          TEXT NOT NULL,
        field                TEXT NOT NULL,
        old_value            TEXT,
        proposed_value       TEXT NOT NULL,
        confidence_score     INTEGER NOT NULL DEFAULT 0,
        risk_level           TEXT NOT NULL DEFAULT 'medium',
        expected_impact_json TEXT NOT NULL DEFAULT '{}',
        explanation_json     TEXT NOT NULL DEFAULT '{}',
        status               TEXT NOT NULL DEFAULT 'pending',
        created_at           TEXT NOT NULL,
        reviewed_at          TEXT,
        applied_at           TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS merchant_learning_settings (
        shop                              TEXT PRIMARY KEY,
        enabled                           INTEGER NOT NULL DEFAULT 1,
        mode                              TEXT NOT NULL DEFAULT 'semi_auto',
        allow_bulk_approval               INTEGER NOT NULL DEFAULT 1,
        max_auto_actions_per_cycle        INTEGER NOT NULL DEFAULT 3,
        min_confidence_to_auto_apply      INTEGER NOT NULL DEFAULT 80,
        min_confidence_to_suggest         INTEGER NOT NULL DEFAULT 45,
        require_approval_for_medium_risk  INTEGER NOT NULL DEFAULT 1,
        updated_at                        TEXT NOT NULL
    )""",
]

# ── Postgres DDL ───────────────────────────────────────────────────────────────
_PG_SHOP_CONFIG = """CREATE TABLE IF NOT EXISTS shop_config (
    shop  TEXT NOT NULL,
    key   TEXT NOT NULL,
    value TEXT NOT NULL,
    PRIMARY KEY (shop, key)
)"""
_PG_EMBEDDINGS = [
    "CREATE EXTENSION IF NOT EXISTS vector",
    """CREATE TABLE IF NOT EXISTS product_embeddings (
        id            SERIAL PRIMARY KEY,
        shop          TEXT NOT NULL,
        product_id    TEXT NOT NULL,
        product_title TEXT NOT NULL DEFAULT '',
        embedding     vector(768),
        model         TEXT NOT NULL DEFAULT 'intfloat/multilingual-e5-base',
        created_at    TIMESTAMP NOT NULL DEFAULT NOW(),
        UNIQUE(shop, product_id)
    )""",
    """CREATE TABLE IF NOT EXISTS query_embeddings (
        id         SERIAL PRIMARY KEY,
        shop       TEXT NOT NULL,
        query      TEXT NOT NULL,
        embedding  vector(768),
        model      TEXT NOT NULL DEFAULT 'intfloat/multilingual-e5-base',
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        UNIQUE(shop, query)
    )""",
]

_PG_LLM_METRICS = """CREATE TABLE IF NOT EXISTS llm_metrics (
    id          SERIAL PRIMARY KEY,
    shop        TEXT,
    provider    TEXT NOT NULL,
    model       TEXT NOT NULL,
    tokens_in   INTEGER NOT NULL DEFAULT 0,
    tokens_out  INTEGER NOT NULL DEFAULT 0,
    cost_usd    DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    latency_ms  DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    error       TEXT,
    called_at   TEXT NOT NULL
)"""

_PG_LLM_CACHE = """CREATE TABLE IF NOT EXISTS llm_cache (
    shop           TEXT NOT NULL,
    task_name      TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    content_hash   TEXT NOT NULL,
    response_json  TEXT NOT NULL,
    tokens_in      INTEGER NOT NULL DEFAULT 0,
    tokens_out     INTEGER NOT NULL DEFAULT 0,
    created_at     TEXT NOT NULL,
    expires_at     TEXT NOT NULL,
    PRIMARY KEY (shop, task_name, prompt_version, content_hash)
)"""

_PG_KEYWORD_CACHE = """CREATE TABLE IF NOT EXISTS keyword_data_cache (
    cache_key    TEXT PRIMARY KEY,
    data_type    TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    expires_at   TEXT NOT NULL
)"""

_PG_DDL = [
    """CREATE TABLE IF NOT EXISTS meta_suggestions (
        id                    SERIAL PRIMARY KEY,
        shop                  TEXT NOT NULL,
        product_id            TEXT NOT NULL,
        product_title         TEXT NOT NULL,
        generated_title       TEXT,
        generated_description TEXT,
        provider              TEXT,
        status                TEXT NOT NULL DEFAULT 'pending',
        error                 TEXT,
        job_id                TEXT,
        created_at            TIMESTAMP NOT NULL DEFAULT NOW()
    )""",
    """CREATE TABLE IF NOT EXISTS shop_tokens (
        shop         TEXT PRIMARY KEY,
        access_token TEXT NOT NULL,
        scope        TEXT,
        installed_at TEXT NOT NULL,
        updated_at   TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS google_tokens (
        shop         TEXT PRIMARY KEY,
        token_json   TEXT NOT NULL,
        scopes       TEXT,
        email        TEXT,
        created_at   TEXT NOT NULL,
        updated_at   TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS oauth_states (
        state      TEXT PRIMARY KEY,
        created_at DOUBLE PRECISION NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS seo_changes (
        id            SERIAL PRIMARY KEY,
        shop          TEXT,
        applied_at    TEXT NOT NULL,
        resource_type TEXT NOT NULL,
        resource_id   TEXT NOT NULL,
        field         TEXT NOT NULL,
        old_value     TEXT,
        new_value     TEXT,
        status        TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS snapshots (
        id            SERIAL PRIMARY KEY,
        shop          TEXT,
        snapshot_date TEXT NOT NULL,
        resource_type TEXT NOT NULL,
        resource_id   TEXT NOT NULL,
        data_json     TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS gdpr_requests (
        id          SERIAL PRIMARY KEY,
        received_at TEXT NOT NULL,
        topic       TEXT NOT NULL,
        shop        TEXT NOT NULL,
        payload     TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS subscriptions (
        id              SERIAL PRIMARY KEY,
        shop            TEXT NOT NULL UNIQUE,
        subscription_id TEXT,
        plan            TEXT NOT NULL DEFAULT 'free',
        status          TEXT NOT NULL DEFAULT 'pending',
        created_at      TEXT NOT NULL,
        updated_at      TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS jobs (
        id           TEXT PRIMARY KEY,
        queue        TEXT NOT NULL,
        payload      TEXT NOT NULL,
        shop         TEXT,
        status       TEXT NOT NULL DEFAULT 'pending',
        priority     INTEGER NOT NULL DEFAULT 0,
        retries      INTEGER NOT NULL DEFAULT 0,
        max_retries  INTEGER NOT NULL DEFAULT 3,
        scheduled_at TEXT NOT NULL,
        started_at   TEXT,
        completed_at TEXT,
        result       TEXT,
        created_at   TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS geo_impact_events (
        id                 SERIAL PRIMARY KEY,
        shop               TEXT NOT NULL,
        created_at         TEXT NOT NULL,
        event_type         TEXT NOT NULL,
        resource_type      TEXT NOT NULL,
        resource_id        TEXT NOT NULL,
        resource_title     TEXT NOT NULL DEFAULT '',
        action_type        TEXT NOT NULL,
        status             TEXT NOT NULL DEFAULT 'planned',
        source             TEXT NOT NULL DEFAULT 'geo',
        job_id             TEXT,
        snapshot_id        INTEGER,
        hypothesis         TEXT,
        score_before       INTEGER,
        score_after        INTEGER,
        measurement_status TEXT NOT NULL DEFAULT 'not_started',
        status_history     TEXT,
        before_snapshot    TEXT NOT NULL,
        after_snapshot     TEXT,
        metrics_before     TEXT NOT NULL,
        metrics_after      TEXT,
        estimated_impact   TEXT NOT NULL,
        observed_impact    TEXT,
        notes              TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS geo_optimization_snapshots (
        id                 SERIAL PRIMARY KEY,
        shop               TEXT NOT NULL,
        created_at         TEXT NOT NULL,
        resource_type      TEXT NOT NULL,
        resource_id        TEXT NOT NULL,
        resource_title     TEXT NOT NULL DEFAULT '',
        action_type        TEXT NOT NULL,
        source             TEXT NOT NULL DEFAULT 'geo',
        hypothesis         TEXT,
        snapshot_json      TEXT NOT NULL,
        metrics_json       TEXT NOT NULL,
        readiness_score    INTEGER NOT NULL DEFAULT 0,
        seo_score          INTEGER NOT NULL DEFAULT 0,
        content_hash       TEXT NOT NULL DEFAULT '',
        notes              TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS crawl_findings (
        id            SERIAL PRIMARY KEY,
        shop          TEXT NOT NULL,
        created_at    TEXT NOT NULL,
        source        TEXT NOT NULL DEFAULT 'crawl_l3',
        url           TEXT NOT NULL,
        issue_type    TEXT NOT NULL,
        severity      TEXT NOT NULL,
        detail        TEXT NOT NULL,
        metadata_json TEXT NOT NULL DEFAULT '{}'
    )""",
    """CREATE TABLE IF NOT EXISTS competitor_crawl_cache (
        id                SERIAL PRIMARY KEY,
        url               TEXT NOT NULL UNIQUE,
        domain            TEXT NOT NULL,
        fetched_at        TEXT NOT NULL,
        status_code       INTEGER,
        final_url         TEXT,
        allowed_by_robots BOOLEAN NOT NULL DEFAULT FALSE,
        html_hash         TEXT NOT NULL DEFAULT '',
        features_json     TEXT NOT NULL DEFAULT '{}',
        error             TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS competitor_crawl_runs (
        id              SERIAL PRIMARY KEY,
        shop            TEXT NOT NULL,
        created_at      TEXT NOT NULL,
        enabled         BOOLEAN NOT NULL DEFAULT FALSE,
        urls_selected   INTEGER NOT NULL DEFAULT 0,
        urls_fetched    INTEGER NOT NULL DEFAULT 0,
        urls_from_cache INTEGER NOT NULL DEFAULT 0,
        errors_count    INTEGER NOT NULL DEFAULT 0,
        summary_json    TEXT NOT NULL DEFAULT '{}'
    )""",
    """CREATE TABLE IF NOT EXISTS llms_txt_publications (
        shop                 TEXT PRIMARY KEY,
        theme_id             TEXT,
        agents_hash          TEXT,
        llms_hash            TEXT,
        full_hash            TEXT,
        last_published_at    TEXT,
        last_webhook_tick_at TEXT,
        is_published         INTEGER NOT NULL DEFAULT 0
    )""",
    """CREATE TABLE IF NOT EXISTS product_improvement_tags (
        shop                TEXT NOT NULL,
        product_id          TEXT NOT NULL,
        tag_id              TEXT NOT NULL,
        label               TEXT NOT NULL,
        tag_type            TEXT NOT NULL,
        status              TEXT NOT NULL DEFAULT 'neutral',
        score               INTEGER NOT NULL DEFAULT 0,
        source              TEXT NOT NULL DEFAULT 'market_analysis',
        locked_by_merchant  INTEGER NOT NULL DEFAULT 0,
        reason              TEXT,
        first_seen_at       TEXT NOT NULL,
        last_seen_at        TEXT NOT NULL,
        updated_at          TEXT NOT NULL,
        PRIMARY KEY (shop, product_id, tag_id)
    )""",
    """CREATE TABLE IF NOT EXISTS tag_performance_history (
        id             SERIAL PRIMARY KEY,
        shop           TEXT NOT NULL,
        product_id     TEXT NOT NULL,
        tag_id         TEXT NOT NULL,
        label          TEXT NOT NULL,
        status_before  TEXT NOT NULL,
        status_after   TEXT NOT NULL,
        measurement_window TEXT NOT NULL,
        metrics_json   TEXT NOT NULL DEFAULT '{}',
        reason         TEXT NOT NULL DEFAULT '',
        decided_at     TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS continuous_improvement_agent_runs (
        id             SERIAL PRIMARY KEY,
        shop           TEXT NOT NULL,
        created_at     TEXT NOT NULL,
        mode           TEXT NOT NULL DEFAULT 'semi_auto',
        status         TEXT NOT NULL DEFAULT 'completed',
        summary_json   TEXT NOT NULL DEFAULT '{}',
        proposals_json TEXT NOT NULL DEFAULT '[]',
        errors_json    TEXT NOT NULL DEFAULT '[]'
    )""",
    """CREATE TABLE IF NOT EXISTS learning_observations (
        id                   SERIAL PRIMARY KEY,
        shop                 TEXT NOT NULL,
        ledger_event_id      INTEGER,
        resource_type        TEXT NOT NULL,
        resource_id          TEXT NOT NULL,
        action_type          TEXT NOT NULL,
        surface              TEXT NOT NULL,
        keyword_source       TEXT NOT NULL,
        before_metrics_json  TEXT NOT NULL DEFAULT '{}',
        after_metrics_json   TEXT NOT NULL DEFAULT '{}',
        control_metrics_json TEXT NOT NULL DEFAULT '{}',
        window_days          INTEGER NOT NULL,
        window_label         TEXT NOT NULL,
        is_primary_window    BOOLEAN NOT NULL DEFAULT FALSE,
        outcome_score        DOUBLE PRECISION NOT NULL DEFAULT 0,
        confidence_score     INTEGER NOT NULL DEFAULT 0,
        metadata_json        TEXT NOT NULL DEFAULT '{}',
        created_at           TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS learning_weights (
        id            SERIAL PRIMARY KEY,
        scope         TEXT NOT NULL,
        shop          TEXT,
        feature_key   TEXT NOT NULL,
        feature_value TEXT NOT NULL,
        weight        DOUBLE PRECISION NOT NULL DEFAULT 0,
        sample_size   INTEGER NOT NULL DEFAULT 0,
        confidence    INTEGER NOT NULL DEFAULT 0,
        updated_at    TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS learning_runs (
        id                     SERIAL PRIMARY KEY,
        shop                   TEXT NOT NULL,
        status                 TEXT NOT NULL,
        observations_created   INTEGER NOT NULL DEFAULT 0,
        weights_updated        INTEGER NOT NULL DEFAULT 0,
        actions_reprioritized  INTEGER NOT NULL DEFAULT 0,
        approvals_created      INTEGER NOT NULL DEFAULT 0,
        auto_applied_count     INTEGER NOT NULL DEFAULT 0,
        errors_json            TEXT NOT NULL DEFAULT '[]',
        created_at             TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS learning_policy_decisions (
        id                 SERIAL PRIMARY KEY,
        shop               TEXT NOT NULL,
        resource_id        TEXT NOT NULL,
        action_type        TEXT NOT NULL,
        previous_score     DOUBLE PRECISION NOT NULL DEFAULT 0,
        learning_score     DOUBLE PRECISION NOT NULL DEFAULT 0,
        final_score        DOUBLE PRECISION NOT NULL DEFAULT 0,
        mode               TEXT NOT NULL DEFAULT 'semi_auto',
        approval_required  BOOLEAN NOT NULL DEFAULT TRUE,
        risk_level         TEXT NOT NULL DEFAULT 'medium',
        merchant_decision  TEXT NOT NULL DEFAULT 'pending',
        explanation_json   TEXT NOT NULL DEFAULT '{}',
        applied_at         TEXT,
        reviewed_at        TEXT,
        created_at         TEXT NOT NULL
    )""",
    """CREATE TABLE IF NOT EXISTS learning_pending_approvals (
        id                   SERIAL PRIMARY KEY,
        shop                 TEXT NOT NULL,
        resource_type        TEXT NOT NULL,
        resource_id          TEXT NOT NULL,
        action_type          TEXT NOT NULL,
        field                TEXT NOT NULL,
        old_value            TEXT,
        proposed_value       TEXT NOT NULL,
        confidence_score     INTEGER NOT NULL DEFAULT 0,
        risk_level           TEXT NOT NULL DEFAULT 'medium',
        expected_impact_json TEXT NOT NULL DEFAULT '{}',
        explanation_json     TEXT NOT NULL DEFAULT '{}',
        status               TEXT NOT NULL DEFAULT 'pending',
        created_at           TEXT NOT NULL,
        reviewed_at          TEXT,
        applied_at           TEXT
    )""",
    """CREATE TABLE IF NOT EXISTS merchant_learning_settings (
        shop                              TEXT PRIMARY KEY,
        enabled                           BOOLEAN NOT NULL DEFAULT TRUE,
        mode                              TEXT NOT NULL DEFAULT 'semi_auto',
        allow_bulk_approval               BOOLEAN NOT NULL DEFAULT TRUE,
        max_auto_actions_per_cycle        INTEGER NOT NULL DEFAULT 3,
        min_confidence_to_auto_apply      INTEGER NOT NULL DEFAULT 80,
        min_confidence_to_suggest         INTEGER NOT NULL DEFAULT 45,
        require_approval_for_medium_risk  BOOLEAN NOT NULL DEFAULT TRUE,
        updated_at                        TEXT NOT NULL
    )""",
]


# ── Migrations ────────────────────────────────────────────────────────────────
# Idempotent ALTER TABLE for tables that pre-date the multi-tenant `shop` column.
# Run after CREATE TABLE IF NOT EXISTS so brand-new tables already have the column.

_TABLES_NEEDING_SHOP_COLUMN = ("seo_changes", "snapshots")
_GEO_IMPACT_EVENT_COLUMNS = {
    "snapshot_id": "INTEGER",
    "score_before": "INTEGER",
    "score_after": "INTEGER",
    "measurement_status": "TEXT NOT NULL DEFAULT 'not_started'",
    "status_history": "TEXT",
}
_LEARNING_OBSERVATION_COLUMNS = {
    "ledger_event_id": "INTEGER",
    "metadata_json": "TEXT NOT NULL DEFAULT '{}'",
}


def _sqlite_has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    """Return True if `table.column` exists (SQLite introspection via pragma)."""
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return any(r[1] == column for r in rows)


def _migrate_sqlite_add_shop_columns(conn: sqlite3.Connection) -> None:
    """Add the multi-tenant `shop` column to legacy tables if missing."""
    for table in _TABLES_NEEDING_SHOP_COLUMN:
        if not _sqlite_has_column(conn, table, "shop"):
            conn.execute(f"ALTER TABLE {table} ADD COLUMN shop TEXT")


def _migrate_sqlite_geo_impact_events(conn: sqlite3.Connection) -> None:
    """Add optimization tracking columns to legacy GEO impact ledgers."""
    for column, definition in _GEO_IMPACT_EVENT_COLUMNS.items():
        if not _sqlite_has_column(conn, "geo_impact_events", column):
            conn.execute(f"ALTER TABLE geo_impact_events ADD COLUMN {column} {definition}")


def _migrate_sqlite_learning_observations(conn: sqlite3.Connection) -> None:
    """Add experiment tracking columns to legacy learning observations."""
    for column, definition in _LEARNING_OBSERVATION_COLUMNS.items():
        if not _sqlite_has_column(conn, "learning_observations", column):
            conn.execute(f"ALTER TABLE learning_observations ADD COLUMN {column} {definition}")


def _pg_has_column(cur, table: str, column: str) -> bool:
    """Return True if `table.column` exists (Postgres information_schema)."""
    cur.execute(
        "SELECT 1 FROM information_schema.columns WHERE table_name = %s AND column_name = %s",
        (table, column),
    )
    return cur.fetchone() is not None


def _migrate_postgres_add_shop_columns(cur) -> None:
    """Add the multi-tenant `shop` column to legacy Postgres tables if missing."""
    for table in _TABLES_NEEDING_SHOP_COLUMN:
        if not _pg_has_column(cur, table, "shop"):
            cur.execute(f"ALTER TABLE {table} ADD COLUMN shop TEXT")


def _migrate_postgres_geo_impact_events(cur) -> None:
    """Add optimization tracking columns to legacy GEO impact ledgers."""
    for column, definition in _GEO_IMPACT_EVENT_COLUMNS.items():
        if not _pg_has_column(cur, "geo_impact_events", column):
            cur.execute(f"ALTER TABLE geo_impact_events ADD COLUMN {column} {definition}")


def _migrate_postgres_learning_observations(cur) -> None:
    """Add experiment tracking columns to legacy learning observations."""
    for column, definition in _LEARNING_OBSERVATION_COLUMNS.items():
        if not _pg_has_column(cur, "learning_observations", column):
            cur.execute(f"ALTER TABLE learning_observations ADD COLUMN {column} {definition}")


def _init_postgres(database_url: str) -> None:
    import psycopg2  # noqa: PLC0415

    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            for stmt in _PG_DDL:
                cur.execute(stmt)
            cur.execute(_PG_LLM_METRICS)
            cur.execute(_PG_LLM_CACHE)
            cur.execute(_PG_KEYWORD_CACHE)
            for stmt in _PG_EMBEDDINGS:
                cur.execute(stmt)
            cur.execute(_PG_SHOP_CONFIG)
            _migrate_postgres_add_shop_columns(cur)
            _migrate_postgres_geo_impact_events(cur)
            _migrate_postgres_learning_observations(cur)
        conn.commit()


def init_db(db_path: Path | None = None) -> None:
    """Create every table the app depends on if missing.

    Args:
        db_path: Explicit SQLite path (tests only). When None, uses Postgres if
                 DATABASE_URL is set, otherwise SQLite at the default data/history.db.
    """
    if db_path is None:
        database_url = os.getenv("DATABASE_URL")
        if database_url:
            _init_postgres(database_url)
            return
        db_path = DB_PATH

    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        for stmt in _SQLITE_DDL:
            conn.execute(stmt)
        _migrate_sqlite_add_shop_columns(conn)
        _migrate_sqlite_geo_impact_events(conn)
        _migrate_sqlite_learning_observations(conn)
