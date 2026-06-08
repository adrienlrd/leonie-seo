"""Topic clustering for blog ideas and drafts."""

from __future__ import annotations

from app.blog.clusters import build_blog_idea_clusters


def test_build_blog_idea_clusters_groups_similar_keywords_and_picks_richest_pillar() -> None:
    items = [
        {
            "key": "idea-1",
            "target_keyword": "croquettes sans céréales chien sensible",
            "outline": ["A"],
        },
        {
            "key": "idea-2",
            "target_keyword": "croquettes sans céréales pour chien",
            "outline": ["A", "B", "C", "D"],
        },
        {
            "key": "idea-3",
            "target_keyword": "litière chat intérieur",
            "outline": ["A", "B"],
        },
    ]

    clusters = build_blog_idea_clusters(items)

    assert len(clusters) == 1
    cluster = clusters[0]
    assert cluster["pillar_key"] == "idea-2"
    assert set(cluster["member_keys"]) == {"idea-1", "idea-2"}
    assert cluster["head_keyword"]


def test_build_blog_idea_clusters_drops_singletons() -> None:
    items = [
        {"key": "idea-1", "target_keyword": "croquettes sans céréales chien", "outline": ["A"]},
        {"key": "idea-2", "target_keyword": "litière chat intérieur", "outline": ["A"]},
        {"key": "idea-3", "target_keyword": "panier chien hiver", "outline": ["A"]},
    ]

    assert build_blog_idea_clusters(items) == []


def test_build_blog_idea_clusters_skips_items_without_keyword_or_key() -> None:
    items = [
        {"key": "idea-1", "target_keyword": "", "outline": ["A"]},
        {"key": "", "target_keyword": "croquettes sans céréales chien", "outline": ["A"]},
    ]

    assert build_blog_idea_clusters(items) == []
