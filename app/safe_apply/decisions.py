"""Human decision persistence for content actions — accept / edit / reject / retry."""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.content_actions.schema import ContentActionResult

_MAX_RETRIES = 3
_VALID_DECISIONS = frozenset({"accept", "edit", "reject", "retry"})


def _blocked_reasons(constraints_check) -> list[str]:
    reasons: list[str] = []
    if constraints_check.forbidden_promise_violations:
        reasons.append(
            "forbidden_promise: " + ", ".join(constraints_check.forbidden_promise_violations)
        )
    if constraints_check.do_not_say_violations:
        reasons.append("do_not_say: " + ", ".join(constraints_check.do_not_say_violations))
    if not constraints_check.length_ok:
        reasons.append("length_out_of_bounds")
    if not constraints_check.language_ok:
        reasons.append("language_mismatch")
    return reasons


def _sha16(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def _retry_count(shop: str, action_id: str, path: Path) -> int:
    from app.db_adapter import get_conn  # noqa: PLC0415

    try:
        with get_conn(path) as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS cnt FROM content_action_decisions "
                "WHERE shop = ? AND action_id = ? AND decision = 'retry'",
                (shop, action_id),
            ).fetchone()
        return int(row["cnt"]) if row else 0
    except Exception:
        return 0


def _insert_decision(
    shop: str,
    action_id: str,
    content_type: str,
    decision: str,
    now: str,
    after_hash: str,
    edit_diff: str | None,
    rejected_reason: str | None,
    retry_index: int,
    path: Path,
) -> None:
    from app.db_adapter import get_conn  # noqa: PLC0415

    try:
        with get_conn(path) as conn:
            conn.execute(
                """INSERT INTO content_action_decisions
                   (shop, action_id, content_type, decision, decided_at,
                    after_hash, edit_diff, rejected_reason, retry_index)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    shop,
                    action_id,
                    content_type,
                    decision,
                    now,
                    after_hash,
                    edit_diff,
                    rejected_reason,
                    retry_index,
                ),
            )
    except Exception:
        pass


def record_decision(
    shop: str,
    action_id: str,
    decision: str,
    *,
    edited_text: str | None = None,
    rejected_reason: str | None = None,
    db_path: Path | None = None,
) -> dict:
    """Persist a human review decision on a content action.

    Args:
        shop: Shopify shop domain.
        action_id: ID of the content action.
        decision: One of accept|edit|reject|retry.
        edited_text: Replacement text when decision=edit.
        rejected_reason: Free text when decision=reject.
        db_path: Optional DB path override (tests only).

    Returns:
        Dict with action_id, decision, decided_at, new_status.

    Raises:
        ValueError: If decision is invalid, accept is blocked, or retry limit exceeded.
    """
    from app.content_actions.runner import _load_action, _update_action_status  # noqa: PLC0415
    from app.content_actions.schema import ContentStatus  # noqa: PLC0415
    from app.db_adapter import DB_PATH  # noqa: PLC0415

    if decision not in _VALID_DECISIONS:
        raise ValueError(f"Invalid decision {decision!r}. Expected: {sorted(_VALID_DECISIONS)}.")

    path = db_path if db_path is not None else DB_PATH
    result = _load_action(shop, action_id, db_path=path)
    if result is None:
        raise ValueError(f"Action {action_id!r} not found for shop {shop!r}.")

    current_retries = _retry_count(shop, action_id, path)

    if decision == "retry" and current_retries >= _MAX_RETRIES:
        raise ValueError(
            f"Maximum {_MAX_RETRIES} retries reached. Please edit the content manually."
        )

    if decision == "accept":
        blocked = _blocked_reasons(result.constraints_check)
        if blocked:
            raise ValueError(f"Accept blocked: {'; '.join(blocked)}")

    now = datetime.now(UTC).isoformat()
    after_hash = _sha16(result.output.primary_text)
    edit_diff_json: str | None = None
    new_result: ContentActionResult | None = None

    if decision == "edit" and edited_text is not None:
        updated = copy.deepcopy(result)
        updated.output.primary_text = edited_text
        new_result = updated
        edit_diff_json = json.dumps(
            {"old": result.output.primary_text[:200], "new": edited_text[:200]}
        )
        after_hash = _sha16(edited_text)

    _decision_status = {
        "accept": ContentStatus.APPROVED,
        "edit": ContentStatus.APPROVED,
        "reject": ContentStatus.REJECTED,
        "retry": ContentStatus.DRAFT,
    }
    new_status = _decision_status[decision]

    _insert_decision(
        shop=shop,
        action_id=action_id,
        content_type=result.content_type.value,
        decision=decision,
        now=now,
        after_hash=after_hash,
        edit_diff=edit_diff_json,
        rejected_reason=rejected_reason if decision == "reject" else None,
        retry_index=current_retries + 1 if decision == "retry" else 0,
        path=path,
    )

    _update_action_status(shop, action_id, new_status, new_result, db_path=path)

    return {
        "action_id": action_id,
        "decision": decision,
        "decided_at": now,
        "new_status": new_status.value,
        "retry_index": current_retries + 1 if decision == "retry" else 0,
    }


def get_decision_history(
    shop: str,
    action_id: str,
    *,
    db_path: Path | None = None,
) -> list[dict]:
    """Return all decisions for a content action, newest first."""
    from app.db_adapter import DB_PATH, get_conn  # noqa: PLC0415

    path = db_path if db_path is not None else DB_PATH
    try:
        with get_conn(path) as conn:
            rows = conn.execute(
                """SELECT id, decision, decided_at, edit_diff, rejected_reason, retry_index
                   FROM content_action_decisions
                   WHERE shop = ? AND action_id = ?
                   ORDER BY decided_at DESC""",
                (shop, action_id),
            ).fetchall()
    except Exception:
        return []

    return [
        {
            "id": r["id"],
            "decision": r["decision"],
            "decided_at": r["decided_at"],
            "edit_diff": r["edit_diff"],
            "rejected_reason": r["rejected_reason"],
            "retry_index": r["retry_index"],
        }
        for r in rows
    ]
