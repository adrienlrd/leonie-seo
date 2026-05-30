"""Tests for cross-product keyword cannibalization detection."""

from __future__ import annotations

from app.market_analysis import cannibalization as cn


def _product(
    product_id: str,
    *,
    primary: str,
    opportunity: int = 50,
    gsc_impressions: int = 0,
    secondary: list[str] | None = None,
) -> dict:
    keywords: list[dict] = []
    if primary:
        keywords.append(
            {
                "query": primary,
                "target_role": "primary",
                "gsc_impressions": gsc_impressions,
            }
        )
    for kw in secondary or []:
        keywords.append({"query": kw, "target_role": "secondary"})
    return {
        "product_id": product_id,
        "product_title": product_id.replace("-", " ").title(),
        "product_url": f"/products/{product_id}",
        "seo_keywords": keywords,
        "opportunity_score": opportunity,
    }


class TestDetectAlerts:
    def test_no_alert_when_each_primary_is_unique(self):
        products = [
            _product("croquettes-bio", primary="croquettes bio chien"),
            _product("harnais-cuir", primary="harnais cuir chien"),
        ]
        assert cn.detect_alerts(products) == []

    def test_alert_when_two_products_share_exact_primary(self):
        products = [
            _product("harnais-cuir-a", primary="harnais chien", opportunity=80),
            _product("harnais-tissu-b", primary="harnais chien", opportunity=60),
        ]
        alerts = cn.detect_alerts(products)
        assert len(alerts) == 1
        alert = alerts[0]
        assert alert["cluster_head"] == "harnais chien"
        assert sorted(alert["product_ids"]) == ["harnais-cuir-a", "harnais-tissu-b"]
        assert alert["winner_suggested"] == "harnais-cuir-a"
        assert alert["action"] == "reorient_secondary"

    def test_alert_when_products_share_lemma_variant(self):
        # Plural and singular collapse to the same stem → cannibalization.
        products = [
            _product("a", primary="croquettes chien", opportunity=70),
            _product("b", primary="croquette chien", opportunity=50),
        ]
        alerts = cn.detect_alerts(products)
        assert len(alerts) == 1
        assert alerts[0]["winner_suggested"] == "a"

    def test_winner_prefers_higher_gsc_impressions_over_opportunity_score(self):
        products = [
            _product("a", primary="harnais chien", opportunity=50, gsc_impressions=900),
            _product("b", primary="harnais chien", opportunity=90, gsc_impressions=10),
        ]
        alerts = cn.detect_alerts(products)
        assert alerts[0]["winner_suggested"] == "a"

    def test_alert_groups_three_products_in_one_entry(self):
        products = [
            _product("a", primary="harnais chien", opportunity=80),
            _product("b", primary="harnais chien", opportunity=60),
            _product("c", primary="harnais chien", opportunity=40),
        ]
        alerts = cn.detect_alerts(products)
        assert len(alerts) == 1
        assert len(alerts[0]["product_ids"]) == 3

    def test_secondary_keyword_overlap_does_not_trigger_alert(self):
        # Only `primary` keywords drive cannibalization (secondary roles allowed to share).
        products = [
            _product("a", primary="croquettes chien", secondary=["harnais chien"]),
            _product("b", primary="harnais chien"),
        ]
        # b's primary == a's secondary — that's reuse, not cannibalization.
        alerts = cn.detect_alerts(products)
        assert alerts == []

    def test_ignores_products_without_primary_keyword(self):
        products = [
            _product("a", primary=""),
            _product("b", primary=""),
        ]
        assert cn.detect_alerts(products) == []

    def test_empty_input_returns_empty_list(self):
        assert cn.detect_alerts([]) == []


class TestReorientHint:
    def test_loser_receives_longtail_redirect_hint(self):
        products = [
            _product("winner-id", primary="harnais chien", opportunity=80),
            _product(
                "loser-id",
                primary="harnais chien",
                opportunity=40,
                secondary=["harnais cuir chien moyen gabarit"],
            ),
        ]
        alerts = cn.detect_alerts(products)
        loser_hint = cn.get_reorientation_hint(alerts, product_id="loser-id")
        assert loser_hint is not None
        assert loser_hint["cluster_head"] == "harnais chien"
        assert loser_hint["target_role"] == "secondary"
        # Suggests pivoting to a more specific longtail from the loser's existing list.
        assert "harnais cuir chien moyen gabarit" in loser_hint["pivot_suggestions"]

    def test_winner_receives_no_hint(self):
        products = [
            _product("winner-id", primary="harnais chien", opportunity=80),
            _product("loser-id", primary="harnais chien", opportunity=40),
        ]
        alerts = cn.detect_alerts(products)
        assert cn.get_reorientation_hint(alerts, product_id="winner-id") is None

    def test_unrelated_product_receives_no_hint(self):
        products = [
            _product("a", primary="harnais chien", opportunity=80),
            _product("b", primary="harnais chien", opportunity=40),
        ]
        alerts = cn.detect_alerts(products)
        assert cn.get_reorientation_hint(alerts, product_id="other") is None
