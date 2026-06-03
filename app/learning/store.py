"""Persistence helpers for the learning engine."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.db_adapter import DB_PATH, get_conn
from app.learning.models import (
    ApprovalStatus,
    LearningMode,
    LearningWeight,
    MerchantDecision,
    MerchantLearningSettings,
)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_loads(value: str | None, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return default


def _bool(value: Any) -> bool:
    return (
        bool(int(value)) if isinstance(value, int | str) and str(value).isdigit() else bool(value)
    )


def get_settings(shop: str, *, db_path: Path | None = None) -> MerchantLearningSettings:
    """Return merchant learning settings, creating defaults when absent."""
    path = db_path if db_path is not None else DB_PATH
    with get_conn(path) as conn:
        row = conn.execute(
            "SELECT * FROM merchant_learning_settings WHERE shop = ?",
            (shop,),
        ).fetchone()
        if row is None:
            now = datetime.now(UTC).isoformat()
            conn.execute(
                """
                INSERT INTO merchant_learning_settings (
                    shop, enabled, mode, allow_bulk_approval, max_auto_actions_per_cycle,
                    min_confidence_to_auto_apply, min_confidence_to_suggest,
                    require_approval_for_medium_risk, updated_at
                )
                VALUES (?, ?, 'semi_auto', ?, 3, 80, 45, ?, ?)
                """,
                (shop, True, True, True, now),
            )
            return MerchantLearningSettings(shop=shop)
    return MerchantLearningSettings(
        shop=shop,
        enabled=_bool(row["enabled"]),
        mode=LearningMode(str(row["mode"] or LearningMode.SEMI_AUTO.value)),
        allow_bulk_approval=_bool(row["allow_bulk_approval"]),
        max_auto_actions_per_cycle=int(row["max_auto_actions_per_cycle"] or 3),
        min_confidence_to_auto_apply=int(row["min_confidence_to_auto_apply"] or 80),
        min_confidence_to_suggest=int(row["min_confidence_to_suggest"] or 45),
        require_approval_for_medium_risk=_bool(row["require_approval_for_medium_risk"]),
    )


def update_settings(
    shop: str,
    patch: dict[str, Any],
    *,
    db_path: Path | None = None,
) -> MerchantLearningSettings:
    """Update settings while preserving unsupported keys."""
    current = get_settings(shop, db_path=db_path)
    mode = LearningMode(str(patch.get("mode", current.mode.value)))
    settings = MerchantLearningSettings(
        shop=shop,
        enabled=bool(patch.get("enabled", current.enabled)),
        mode=mode,
        allow_bulk_approval=bool(patch.get("allow_bulk_approval", current.allow_bulk_approval)),
        max_auto_actions_per_cycle=max(
            0, int(patch.get("max_auto_actions_per_cycle", current.max_auto_actions_per_cycle))
        ),
        min_confidence_to_auto_apply=max(
            0,
            min(
                100,
                int(
                    patch.get("min_confidence_to_auto_apply", current.min_confidence_to_auto_apply)
                ),
            ),
        ),
        min_confidence_to_suggest=max(
            0,
            min(
                100, int(patch.get("min_confidence_to_suggest", current.min_confidence_to_suggest))
            ),
        ),
        require_approval_for_medium_risk=bool(
            patch.get(
                "require_approval_for_medium_risk",
                current.require_approval_for_medium_risk,
            )
        ),
    )
    now = datetime.now(UTC).isoformat()
    path = db_path if db_path is not None else DB_PATH
    with get_conn(path) as conn:
        row = conn.execute(
            "SELECT shop FROM merchant_learning_settings WHERE shop = ?",
            (shop,),
        ).fetchone()
        values = (
            settings.enabled,
            settings.mode.value,
            settings.allow_bulk_approval,
            settings.max_auto_actions_per_cycle,
            settings.min_confidence_to_auto_apply,
            settings.min_confidence_to_suggest,
            settings.require_approval_for_medium_risk,
            now,
            shop,
        )
        if row:
            conn.execute(
                """
                UPDATE merchant_learning_settings
                SET enabled = ?, mode = ?, allow_bulk_approval = ?,
                    max_auto_actions_per_cycle = ?,
                    min_confidence_to_auto_apply = ?,
                    min_confidence_to_suggest = ?,
                    require_approval_for_medium_risk = ?,
                    updated_at = ?
                WHERE shop = ?
                """,
                values,
            )
        else:
            conn.execute(
                """
                INSERT INTO merchant_learning_settings (
                    enabled, mode, allow_bulk_approval, max_auto_actions_per_cycle,
                    min_confidence_to_auto_apply, min_confidence_to_suggest,
                    require_approval_for_medium_risk, updated_at, shop
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                values,
            )
    return settings


def observation_exists(
    *,
    shop: str,
    resource_id: str,
    action_type: str,
    window_label: str,
    db_path: Path | None = None,
) -> bool:
    """Return True when an observation already exists for the event window."""
    path = db_path if db_path is not None else DB_PATH
    with get_conn(path) as conn:
        row = conn.execute(
            """
            SELECT id FROM learning_observations
            WHERE shop = ? AND resource_id = ? AND action_type = ? AND window_label = ?
            LIMIT 1
            """,
            (shop, resource_id, action_type, window_label),
        ).fetchone()
    return row is not None


def create_observation(
    *,
    shop: str,
    resource_type: str,
    resource_id: str,
    action_type: str,
    surface: str,
    keyword_source: str,
    before_metrics: dict[str, Any],
    after_metrics: dict[str, Any],
    control_metrics: dict[str, Any],
    window_days: int,
    window_label: str,
    is_primary_window: bool,
    outcome_score: float,
    confidence_score: int,
    db_path: Path | None = None,
) -> int:
    """Persist one learning observation and return its ID."""
    now = datetime.now(UTC).isoformat()
    path = db_path if db_path is not None else DB_PATH
    with get_conn(path) as conn:
        conn.execute(
            """
            INSERT INTO learning_observations (
                shop, resource_type, resource_id, action_type, surface, keyword_source,
                before_metrics_json, after_metrics_json, control_metrics_json,
                window_days, window_label, is_primary_window, outcome_score,
                confidence_score, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                shop,
                resource_type,
                resource_id,
                action_type,
                surface,
                keyword_source,
                _json_dumps(before_metrics),
                _json_dumps(after_metrics),
                _json_dumps(control_metrics),
                window_days,
                window_label,
                int(is_primary_window),
                outcome_score,
                confidence_score,
                now,
            ),
        )
        row = conn.execute(
            """
            SELECT id FROM learning_observations
            WHERE shop = ? AND created_at = ?
            ORDER BY id DESC LIMIT 1
            """,
            (shop, now),
        ).fetchone()
    return int((row or {}).get("id", 0))


def list_observations(
    shop: str,
    *,
    limit: int = 200,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """List recent learning observations."""
    path = db_path if db_path is not None else DB_PATH
    with get_conn(path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM learning_observations
            WHERE shop = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (shop, limit),
        ).fetchall()
    return [
        {
            **row,
            "before_metrics": _json_loads(row.get("before_metrics_json"), {}),
            "after_metrics": _json_loads(row.get("after_metrics_json"), {}),
            "control_metrics": _json_loads(row.get("control_metrics_json"), {}),
            "is_primary_window": _bool(row.get("is_primary_window")),
        }
        for row in rows
    ]


def get_weight(
    *,
    scope: str,
    shop: str | None,
    feature_key: str,
    feature_value: str,
    db_path: Path | None = None,
) -> LearningWeight | None:
    """Load one learning weight."""
    path = db_path if db_path is not None else DB_PATH
    if scope == "merchant":
        sql = """
            SELECT * FROM learning_weights
            WHERE scope = ? AND shop = ? AND feature_key = ? AND feature_value = ?
            LIMIT 1
        """
        params = (scope, shop, feature_key, feature_value)
    else:
        sql = """
            SELECT * FROM learning_weights
            WHERE scope = ? AND shop IS NULL AND feature_key = ? AND feature_value = ?
            LIMIT 1
        """
        params = (scope, feature_key, feature_value)
    with get_conn(path) as conn:
        row = conn.execute(sql, params).fetchone()
    if not row:
        return None
    return LearningWeight(
        scope=str(row["scope"]),
        shop=row["shop"],
        feature_key=str(row["feature_key"]),
        feature_value=str(row["feature_value"]),
        weight=float(row["weight"] or 0.0),
        sample_size=int(row["sample_size"] or 0),
        confidence=int(row["confidence"] or 0),
    )


def upsert_weight(
    *,
    scope: str,
    shop: str | None,
    feature_key: str,
    feature_value: str,
    weight: float,
    sample_size: int,
    confidence: int,
    db_path: Path | None = None,
) -> None:
    """Persist a learning weight."""
    now = datetime.now(UTC).isoformat()
    path = db_path if db_path is not None else DB_PATH
    with get_conn(path) as conn:
        existing = get_weight(
            scope=scope,
            shop=shop,
            feature_key=feature_key,
            feature_value=feature_value,
            db_path=path,
        )
        if existing:
            if scope == "merchant":
                conn.execute(
                    """
                    UPDATE learning_weights
                    SET weight = ?, sample_size = ?, confidence = ?, updated_at = ?
                    WHERE scope = ? AND shop = ? AND feature_key = ? AND feature_value = ?
                    """,
                    (weight, sample_size, confidence, now, scope, shop, feature_key, feature_value),
                )
            else:
                conn.execute(
                    """
                    UPDATE learning_weights
                    SET weight = ?, sample_size = ?, confidence = ?, updated_at = ?
                    WHERE scope = ? AND shop IS NULL AND feature_key = ? AND feature_value = ?
                    """,
                    (weight, sample_size, confidence, now, scope, feature_key, feature_value),
                )
        else:
            conn.execute(
                """
                INSERT INTO learning_weights (
                    scope, shop, feature_key, feature_value, weight, sample_size,
                    confidence, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (scope, shop, feature_key, feature_value, weight, sample_size, confidence, now),
            )


def list_weights(
    shop: str,
    *,
    limit: int = 200,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """List merchant and global learning weights."""
    path = db_path if db_path is not None else DB_PATH
    with get_conn(path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM learning_weights
            WHERE (scope = 'merchant' AND shop = ?) OR scope = 'global'
            ORDER BY ABS(weight) DESC, sample_size DESC
            LIMIT ?
            """,
            (shop, limit),
        ).fetchall()
    return rows


def record_decision(
    *,
    shop: str,
    resource_id: str,
    action_type: str,
    previous_score: float,
    learning_score: float,
    final_score: float,
    mode: str,
    approval_required: bool,
    risk_level: str,
    merchant_decision: str = MerchantDecision.PENDING.value,
    explanation: dict[str, Any] | None = None,
    db_path: Path | None = None,
) -> int:
    """Persist one policy decision."""
    now = datetime.now(UTC).isoformat()
    path = db_path if db_path is not None else DB_PATH
    with get_conn(path) as conn:
        conn.execute(
            """
            INSERT INTO learning_policy_decisions (
                shop, resource_id, action_type, previous_score, learning_score,
                final_score, mode, approval_required, risk_level, merchant_decision,
                explanation_json, applied_at, reviewed_at, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?)
            """,
            (
                shop,
                resource_id,
                action_type,
                previous_score,
                learning_score,
                final_score,
                mode,
                int(approval_required),
                risk_level,
                merchant_decision,
                _json_dumps(explanation or {}),
                now,
            ),
        )
        row = conn.execute(
            """
            SELECT id FROM learning_policy_decisions
            WHERE shop = ? AND created_at = ?
            ORDER BY id DESC LIMIT 1
            """,
            (shop, now),
        ).fetchone()
    return int((row or {}).get("id", 0))


def list_decisions(
    shop: str,
    *,
    limit: int = 100,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """List recent policy decisions."""
    path = db_path if db_path is not None else DB_PATH
    with get_conn(path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM learning_policy_decisions
            WHERE shop = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (shop, limit),
        ).fetchall()
    return [
        {
            **row,
            "approval_required": _bool(row.get("approval_required")),
            "explanation": _json_loads(row.get("explanation_json"), {}),
        }
        for row in rows
    ]


def create_pending_approval(
    *,
    shop: str,
    resource_type: str,
    resource_id: str,
    action_type: str,
    field: str,
    old_value: str,
    proposed_value: str,
    confidence_score: int,
    risk_level: str,
    expected_impact: dict[str, Any],
    explanation: dict[str, Any],
    db_path: Path | None = None,
) -> int:
    """Create one pending merchant approval unless an identical one is open."""
    now = datetime.now(UTC).isoformat()
    path = db_path if db_path is not None else DB_PATH
    with get_conn(path) as conn:
        row = conn.execute(
            """
            SELECT id FROM learning_pending_approvals
            WHERE shop = ? AND resource_id = ? AND action_type = ? AND field = ?
              AND status = 'pending'
            ORDER BY id DESC LIMIT 1
            """,
            (shop, resource_id, action_type, field),
        ).fetchone()
        if row:
            return int(row["id"])
        conn.execute(
            """
            INSERT INTO learning_pending_approvals (
                shop, resource_type, resource_id, action_type, field, old_value,
                proposed_value, confidence_score, risk_level, expected_impact_json,
                explanation_json, status, created_at, reviewed_at, applied_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, NULL, NULL)
            """,
            (
                shop,
                resource_type,
                resource_id,
                action_type,
                field,
                old_value,
                proposed_value,
                confidence_score,
                risk_level,
                _json_dumps(expected_impact),
                _json_dumps(explanation),
                now,
            ),
        )
        created = conn.execute(
            """
            SELECT id FROM learning_pending_approvals
            WHERE shop = ? AND created_at = ?
            ORDER BY id DESC LIMIT 1
            """,
            (shop, now),
        ).fetchone()
    return int((created or {}).get("id", 0))


def list_pending_approvals(
    shop: str,
    *,
    include_closed: bool = False,
    limit: int = 100,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """List pending approvals for the merchant UI."""
    where = "WHERE shop = ?"
    params: list[Any] = [shop]
    if not include_closed:
        where += " AND status = 'pending'"
    params.append(limit)
    path = db_path if db_path is not None else DB_PATH
    with get_conn(path) as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM learning_pending_approvals
            {where}
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            tuple(params),
        ).fetchall()
    return [
        {
            **row,
            "expected_impact": _json_loads(row.get("expected_impact_json"), {}),
            "explanation": _json_loads(row.get("explanation_json"), {}),
        }
        for row in rows
    ]


def update_approval_status(
    *,
    shop: str,
    approval_id: int,
    status: ApprovalStatus,
    proposed_value: str | None = None,
    db_path: Path | None = None,
) -> dict[str, Any] | None:
    """Update approval status and return the updated row."""
    now = datetime.now(UTC).isoformat()
    path = db_path if db_path is not None else DB_PATH
    with get_conn(path) as conn:
        row = conn.execute(
            "SELECT * FROM learning_pending_approvals WHERE shop = ? AND id = ?",
            (shop, approval_id),
        ).fetchone()
        if not row:
            return None
        if proposed_value is not None:
            conn.execute(
                """
                UPDATE learning_pending_approvals
                SET status = ?, proposed_value = ?, reviewed_at = ?
                WHERE shop = ? AND id = ?
                """,
                (status.value, proposed_value, now, shop, approval_id),
            )
        else:
            applied_at = now if status == ApprovalStatus.APPLIED else row.get("applied_at")
            conn.execute(
                """
                UPDATE learning_pending_approvals
                SET status = ?, reviewed_at = COALESCE(reviewed_at, ?), applied_at = ?
                WHERE shop = ? AND id = ?
                """,
                (status.value, now, applied_at, shop, approval_id),
            )
        updated = conn.execute(
            "SELECT * FROM learning_pending_approvals WHERE shop = ? AND id = ?",
            (shop, approval_id),
        ).fetchone()
    if not updated:
        return None
    return {
        **updated,
        "expected_impact": _json_loads(updated.get("expected_impact_json"), {}),
        "explanation": _json_loads(updated.get("explanation_json"), {}),
    }


def record_run(
    *,
    shop: str,
    status: str,
    observations_created: int,
    weights_updated: int,
    actions_reprioritized: int,
    approvals_created: int,
    auto_applied_count: int,
    errors: list[dict[str, Any]],
    db_path: Path | None = None,
) -> int:
    """Persist one learning cycle run."""
    now = datetime.now(UTC).isoformat()
    path = db_path if db_path is not None else DB_PATH
    with get_conn(path) as conn:
        conn.execute(
            """
            INSERT INTO learning_runs (
                shop, status, observations_created, weights_updated,
                actions_reprioritized, approvals_created, auto_applied_count,
                errors_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                shop,
                status,
                observations_created,
                weights_updated,
                actions_reprioritized,
                approvals_created,
                auto_applied_count,
                _json_dumps(errors),
                now,
            ),
        )
        row = conn.execute(
            """
            SELECT id FROM learning_runs
            WHERE shop = ? AND created_at = ?
            ORDER BY id DESC LIMIT 1
            """,
            (shop, now),
        ).fetchone()
    return int((row or {}).get("id", 0))


def list_runs(shop: str, *, limit: int = 20, db_path: Path | None = None) -> list[dict[str, Any]]:
    """List recent learning runs."""
    path = db_path if db_path is not None else DB_PATH
    with get_conn(path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM learning_runs
            WHERE shop = ?
            ORDER BY created_at DESC, id DESC
            LIMIT ?
            """,
            (shop, limit),
        ).fetchall()
    return [{**row, "errors": _json_loads(row.get("errors_json"), [])} for row in rows]
