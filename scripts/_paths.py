"""Absolute project paths — survive being invoked from any CWD."""

from pathlib import Path

PROJECT_ROOT = Path(__file__).parents[1]
CONFIG_DIR = PROJECT_ROOT / "config"
SEO_RULES_PATH = str(CONFIG_DIR / "seo_rules.yaml")
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = str(DATA_DIR / "history.db")
RAW_DIR = DATA_DIR / "raw"
REPORTS_DIR = PROJECT_ROOT / "reports"
