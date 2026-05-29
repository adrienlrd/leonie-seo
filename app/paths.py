"""Canonical filesystem paths for the app.

The raw-data directory is configurable via the ``DATA_DIR`` environment variable so
it can point at a mounted persistent disk in production (e.g. Render disk at
``/app/data``). All modules must resolve it through :func:`data_dir` rather than
hardcoding a path, otherwise reads and writes can diverge and data written off the
mounted disk is lost on redeploy.
"""

from __future__ import annotations

import os
from pathlib import Path

_DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


def data_dir() -> Path:
    """Return the raw-data directory, honoring the ``DATA_DIR`` env override."""
    return Path(os.environ.get("DATA_DIR", str(_DEFAULT_DATA_DIR)))
