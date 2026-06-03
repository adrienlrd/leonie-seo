"""Tests for learning mode boundaries."""

from __future__ import annotations

from pathlib import Path


def test_learning_mode_surface_contains_only_two_modes() -> None:
    forbidden = "man" + "ual"
    repo = Path(__file__).parents[2]
    files = [
        repo / "app" / "learning" / "models.py",
        repo / "app" / "api" / "learning.py",
        repo / "shopify-app" / "app" / "routes" / "app.continuous-improvement.tsx",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in files)

    assert "semi_auto" in text
    assert "auto_apply" in text
    assert forbidden not in text.lower()
