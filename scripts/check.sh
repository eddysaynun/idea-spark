#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

command -v node >/dev/null 2>&1 || { echo "ERROR: node is required" >&2; exit 1; }
command -v uv >/dev/null 2>&1 || { echo "ERROR: uv is required" >&2; exit 1; }

if command -v npm >/dev/null 2>&1; then
  PACKAGE_MANAGER="npm"
elif command -v pnpm >/dev/null 2>&1; then
  PACKAGE_MANAGER="pnpm"
else
  echo "ERROR: npm or pnpm is required" >&2
  exit 1
fi

echo "[1/3] Frontend lint, tests, and production build"
(cd "$PROJECT_DIR/frontend" && "$PACKAGE_MANAGER" run check)

echo "[2/3] Backend tests and syntax compilation"
(cd "$PROJECT_DIR/backend" && uv run pytest -q && uv run python -m compileall -q .)

echo "[3/3] Diff whitespace validation"
(cd "$PROJECT_DIR" && git diff --check)

echo "All checks passed."
