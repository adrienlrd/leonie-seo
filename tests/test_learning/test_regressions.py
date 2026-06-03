"""Global regression tests for learning safety contracts."""

from __future__ import annotations

from pathlib import Path

from app.content_actions.schema import ContentType
from app.learning.models import LEARNING_WINDOWS_DAYS, PRIMARY_WINDOW_DAYS, PRIMARY_WINDOW_LABEL
from app.learning.risk import assess_action_risk, is_auto_apply_field_allowed


def test_learning_contract_has_only_semi_auto_and_auto_apply_modes() -> None:
    repo = Path(__file__).parents[2]
    forbidden = "man" + "ual"
    files = [
        repo / "app" / "learning" / "models.py",
        repo / "app" / "learning" / "store.py",
        repo / "app" / "learning" / "policy.py",
        repo / "app" / "api" / "learning.py",
        repo / "app" / "db.py",
        repo / "docs" / "learning-engine.md",
        repo / "shopify-app" / "app" / "routes" / "app.continuous-improvement.tsx",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in files if path.exists()).lower()

    assert "semi_auto" in text
    assert "auto_apply" in text
    assert forbidden not in text
    assert f"learningmode.{forbidden.upper()}" not in text


def test_learning_windows_keep_j14_and_j28_as_decision_windows() -> None:
    assert LEARNING_WINDOWS_DAYS[:2] == (14, 28)
    assert PRIMARY_WINDOW_DAYS == 28
    assert PRIMARY_WINDOW_LABEL == "J+28"


def test_legacy_j7_j30_are_not_learning_primary_windows() -> None:
    repo = Path(__file__).parents[2]
    learning_files = [
        *list((repo / "app" / "learning").glob("*.py")),
        repo / "app" / "geo" / "continuous_agent.py",
        repo / "app" / "geo" / "validation_timeline.py",
        repo / "app" / "geo" / "impact_report.py",
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in learning_files if path.exists())

    assert "J+7" not in text
    assert "J+30" not in text
    assert "PRIMARY_WINDOW_DAYS = 28" in (repo / "app" / "learning" / "models.py").read_text(
        encoding="utf-8"
    )


def test_auto_apply_safe_fields_exclude_risky_surfaces() -> None:
    forbidden_fields = {
        "blog",
        "faq",
        "faq_block",
        "jsonld",
        "jsonld_faqpage",
        "llms.txt",
        "agents.md",
        "alt_text",
        "theme",
        "theme_change",
    }

    for field in forbidden_fields:
        assert is_auto_apply_field_allowed(field) is False

    risky_types = [
        ContentType.BUYING_GUIDE.value,
        ContentType.FAQ_BLOCK.value,
        ContentType.JSONLD_FAQPAGE.value,
        ContentType.ALT_TEXT.value,
    ]
    for action_type in risky_types:
        assert assess_action_risk(action_type).value in {"medium", "high"}


def test_continuous_improvement_ui_learning_contract_is_present() -> None:
    repo = Path(__file__).parents[2]
    ui = repo / "shopify-app" / "app" / "routes" / "app.continuous-improvement.tsx"
    text = ui.read_text(encoding="utf-8")
    forbidden = "man" + "ual"

    assert "Semi-automatique — recommandé" in text
    assert "Auto-apply — avancé" in text
    assert forbidden not in text.lower()
    for label in [
        "Enregistrer",
        "Lancer un cycle maintenant",
        "Appliquer",
        "Ignorer",
        "Modifier",
        "Appliquer toutes les actions sûres",
        "Suivi J+14 / J+28",
    ]:
        assert label in text
    assert "interface LearningStatusData" in text
    assert "interface LearningApproval" in text
