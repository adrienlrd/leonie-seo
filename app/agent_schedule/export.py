"""Full JSON export of agent activity for external analysis.

Aggregates everything needed to understand what the agent proposed, applied,
refused, learned, and which metrics it used — so the merchant can hand the file
to an external assistant (e.g. ChatGPT). Reuses existing read helpers; never
mutates data.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.agent_schedule.evaluation import evaluate_agent_effectiveness
from app.agent_schedule.store import get_schedule
from app.geo.continuous_improvement import list_continuous_improvement
from app.geo.ledger import list_geo_events
from app.learning.store import get_settings, list_pending_approvals, list_runs


def build_export(shop: str, *, db_path: Path | None = None) -> dict[str, Any]:
    """Build a complete, self-contained export payload for one shop."""
    errors: list[dict[str, str]] = []

    def _section(name: str, fn) -> Any:
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — surface, never abort the export
            errors.append({"section": name, "error": str(exc)})
            return None

    schedule = _section("schedule", lambda: get_schedule(shop, db_path=db_path))
    learning_settings = _section("learning_settings", lambda: get_settings(shop, db_path=db_path))
    continuous = _section(
        "continuous_improvement",
        lambda: list_continuous_improvement(shop, limit=300, db_path=db_path),
    )
    learning_runs = _section("learning_runs", lambda: list_runs(shop, limit=20, db_path=db_path))
    pending_approvals = _section(
        "pending_approvals",
        lambda: list_pending_approvals(shop, include_closed=True, limit=200, db_path=db_path),
    )
    geo_events = _section(
        "geo_events",
        lambda: list_geo_events(shop, limit=500, db_path=db_path).get("events", []),
    )
    effectiveness = _section(
        "effectiveness",
        lambda: evaluate_agent_effectiveness(shop, db_path=db_path),
    )

    continuous = continuous or {}
    return {
        "exported_at": datetime.now(UTC).isoformat(),
        "shop": shop,
        "effectiveness": effectiveness,
        "settings": {
            "schedule": schedule.to_dict() if schedule is not None else None,
            "learning": (
                learning_settings.__dict__ | {"mode": learning_settings.mode.value}
                if learning_settings is not None
                else None
            ),
        },
        "summary": continuous.get("summary"),
        "products": continuous.get("products", []),
        "tag_history": continuous.get("tag_history", []),
        "agent_runs": continuous.get("agent_runs", []),
        # continuous_improvement "events" come from the same geo ledger as
        # geo_events — exporting both doubled the file for no information.
        "geo_events": geo_events or [],
        "learning_runs": learning_runs or [],
        "pending_approvals": pending_approvals or [],
        "errors": errors,
    }
