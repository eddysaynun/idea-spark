#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

command -v uv >/dev/null 2>&1 || { echo "ERROR: install uv first: https://docs.astral.sh/uv/" >&2; exit 1; }
command -v node >/dev/null 2>&1 || { echo "ERROR: Node.js is required" >&2; exit 1; }
if command -v npm >/dev/null 2>&1; then
  PACKAGE_MANAGER="npm"
elif command -v pnpm >/dev/null 2>&1; then
  PACKAGE_MANAGER="pnpm"
else
  echo "ERROR: npm or pnpm is required" >&2
  exit 1
fi

if [ ! -d "$PROJECT_DIR/frontend/node_modules" ]; then
  echo "ERROR: frontend dependencies are missing; run: cd frontend && npm ci" >&2
  exit 1
fi

cleanup() {
  trap - INT TERM EXIT
  kill "${BACKEND_PID:-}" "${FRONTEND_PID:-}" 2>/dev/null || true
}
trap cleanup INT TERM EXIT

(cd "$PROJECT_DIR/backend" && uv run python app.py) &
BACKEND_PID=$!
(cd "$PROJECT_DIR/frontend" && "$PACKAGE_MANAGER" run dev) &
FRONTEND_PID=$!

echo "Idea Spark started"
echo "  Web:  http://localhost:3000"
echo "  API:  http://localhost:3001/docs"
echo "Press Ctrl+C to stop both processes."

while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
  sleep 1
done

echo "ERROR: one of the development processes stopped unexpectedly" >&2
exit 1
