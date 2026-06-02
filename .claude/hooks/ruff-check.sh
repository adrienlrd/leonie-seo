#!/usr/bin/env bash
# PostToolUse hook: runs `ruff check` on a Python file edited by Claude.
# Pure validation, no auto-fix. Output (if any) is surfaced back to the model.
#
# AGENTS.md policy:
#   "Hooks are allowed only for validation or safety.
#    Hooks must not be destructive and must not bypass confirmations."
# This script is read-only on the file and project state.

set -u

input=$(cat)

file_path=$(printf '%s' "$input" | jq -r '.tool_input.file_path // empty')

# Bail out if no file path or not a Python file.
[[ -z "$file_path" ]] && exit 0
[[ "$file_path" == *.py ]] || exit 0
[[ -f "$file_path" ]] || exit 0

# ruff auto-discovers pyproject.toml walking up from $file_path.
if ! output=$(ruff check "$file_path" 2>&1); then
    # Non-zero exit code surfaces output to Claude so it can react on next turn.
    printf 'ruff check found issues in %s:\n%s\n' "$file_path" "$output" >&2
    exit 2
fi

exit 0
