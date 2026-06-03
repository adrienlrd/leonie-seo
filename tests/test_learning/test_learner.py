"""Focused tests for the learning weight updater."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.db import init_db
from app.learning.learner import update_weights_from_observation
from app.learning.models import LearningObservation
from app.learning.store import get_weight, upsert_weight

SHOP = "store.myshopify.com"


def _observation(*, confidence: int, outcome: float) -> LearningObservation:
    return LearningObservation(
        shop=SHOP,
        resource_type="product",
        resource_id="gid://shopify/Product/1",
        action_type="meta_title",
        surface="product_page",
        keyword_source="gsc",
        before_metrics={},
        after_metrics={},
        control_metrics={},
        window_days=28,
        window_label="J+28",
        is_primary_window=True,
        outcome_score=outcome,
        confidence_score=confidence,
        features=[("action_type", "meta_title")],
    )


def test_update_weights_from_observation_ignores_low_confidence(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)

    updated = update_weights_from_observation(
        _observation(confidence=20, outcome=90),
        db_path=db,
    )

    assert updated == 0
    assert (
        get_weight(
            scope="merchant",
            shop=SHOP,
            feature_key="action_type",
            feature_value="meta_title",
            db_path=db,
        )
        is None
    )


def test_update_weights_from_observation_updates_merchant_and_global(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)

    updated = update_weights_from_observation(
        _observation(confidence=80, outcome=60),
        db_path=db,
    )

    merchant = get_weight(
        scope="merchant",
        shop=SHOP,
        feature_key="action_type",
        feature_value="meta_title",
        db_path=db,
    )
    global_weight = get_weight(
        scope="global",
        shop=None,
        feature_key="action_type",
        feature_value="meta_title",
        db_path=db,
    )
    assert updated == 2
    assert merchant is not None
    assert global_weight is not None
    assert merchant.shop == SHOP
    assert global_weight.shop is None


def test_update_weights_from_observation_applies_formula(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    upsert_weight(
        scope="merchant",
        shop=SHOP,
        feature_key="action_type",
        feature_value="meta_title",
        weight=0.4,
        sample_size=5,
        confidence=60,
        db_path=db,
    )

    update_weights_from_observation(_observation(confidence=80, outcome=60), db_path=db)

    weight = get_weight(
        scope="merchant",
        shop=SHOP,
        feature_key="action_type",
        feature_value="meta_title",
        db_path=db,
    )
    assert weight is not None
    assert weight.sample_size == 6
    assert weight.weight == pytest.approx(0.4 * 0.85 + 0.6 * 0.15 * 0.8)


def test_update_weights_from_observation_increases_confidence_with_sample_size(
    tmp_path: Path,
) -> None:
    db = tmp_path / "history.db"
    init_db(db)

    update_weights_from_observation(_observation(confidence=80, outcome=60), db_path=db)
    first = get_weight(
        scope="merchant",
        shop=SHOP,
        feature_key="action_type",
        feature_value="meta_title",
        db_path=db,
    )
    update_weights_from_observation(_observation(confidence=80, outcome=60), db_path=db)
    second = get_weight(
        scope="merchant",
        shop=SHOP,
        feature_key="action_type",
        feature_value="meta_title",
        db_path=db,
    )

    assert first is not None
    assert second is not None
    assert second.confidence > first.confidence
    assert second.sample_size == 2


def test_update_weights_from_observation_learns_negative_when_reliable(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)

    update_weights_from_observation(_observation(confidence=90, outcome=-80), db_path=db)

    weight = get_weight(
        scope="merchant",
        shop=SHOP,
        feature_key="action_type",
        feature_value="meta_title",
        db_path=db,
    )
    assert weight is not None
    assert weight.weight < 0


def test_update_weights_from_observation_bounds_weights(tmp_path: Path) -> None:
    db = tmp_path / "history.db"
    init_db(db)
    upsert_weight(
        scope="merchant",
        shop=SHOP,
        feature_key="action_type",
        feature_value="meta_title",
        weight=2.0,
        sample_size=1,
        confidence=20,
        db_path=db,
    )

    update_weights_from_observation(_observation(confidence=100, outcome=100), db_path=db)

    weight = get_weight(
        scope="merchant",
        shop=SHOP,
        feature_key="action_type",
        feature_value="meta_title",
        db_path=db,
    )
    assert weight is not None
    assert -1 <= weight.weight <= 1


def test_update_weights_from_observation_does_not_learn_negative_when_confidence_is_low(
    tmp_path: Path,
) -> None:
    db = tmp_path / "history.db"
    init_db(db)

    update_weights_from_observation(_observation(confidence=34, outcome=-100), db_path=db)

    assert (
        get_weight(
            scope="merchant",
            shop=SHOP,
            feature_key="action_type",
            feature_value="meta_title",
            db_path=db,
        )
        is None
    )
