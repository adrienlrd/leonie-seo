#!/usr/bin/env bash
# install.sh — one-command bootstrap for leonie-seo
set -euo pipefail

REQUIRED_PY="3.11"
VENV_DIR=".venv"

# ── Python version check ──────────────────────────────────────────────────────
check_python() {
    local py_cmd
    for py_cmd in python3.12 python3.11 python3; do
        if command -v "$py_cmd" &>/dev/null; then
            local version
            version=$("$py_cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
            local major minor
            major=$(echo "$version" | cut -d. -f1)
            minor=$(echo "$version" | cut -d. -f2)
            if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
                echo "$py_cmd"
                return
            fi
        fi
    done
    echo ""
}

echo ""
echo "  leonie-seo — SEO automation for Shopify boutiques"
echo "  ─────────────────────────────────────────────────"
echo ""

PY=$(check_python)
if [ -z "$PY" ]; then
    echo "  ✗ Python ${REQUIRED_PY}+ not found."
    echo "    Install it from https://www.python.org or via your package manager."
    exit 1
fi
echo "  ✓ Python found : $($PY --version)"

# ── Virtual environment ───────────────────────────────────────────────────────
if [ ! -d "$VENV_DIR" ]; then
    echo "  → Creating virtual environment in ${VENV_DIR}/ ..."
    "$PY" -m venv "$VENV_DIR"
fi

source "${VENV_DIR}/bin/activate"
echo "  ✓ Virtual environment activated"

# ── Install package ───────────────────────────────────────────────────────────
echo "  → Installing leonie-seo ..."
pip install --quiet --upgrade pip
pip install --quiet -e ".[dev]"
echo "  ✓ leonie-seo installed"

# ── .env bootstrap ───────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "  ✓ .env created from .env.example — fill in your credentials"
else
    echo "  ✓ .env already exists"
fi

echo ""
echo "  All done! Run: source ${VENV_DIR}/bin/activate && leonie-seo --help"
echo ""
