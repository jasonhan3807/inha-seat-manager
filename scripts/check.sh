#!/usr/bin/env bash
# 전체 자동 점검: 단위/API 테스트 + (선택) 브라우저 UI 점검
# 사용법: scripts/check.sh            # 테스트만
#        scripts/check.sh --ui       # 서버를 잠시 띄워 PC/모바일 UI 점검까지
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"; cd "$ROOT"
PY="${PYTHON:-.venv/bin/python}"

echo "== 1. pytest"
"$PY" -m pytest -q -p no:warnings

if [ "${1:-}" = "--ui" ]; then
  echo "== 2. UI 점검 (Playwright)"
  TMP="$(mktemp -d)"
  PORT=8765
  DB_PATH="$TMP/ui.db" PORT=$PORT MONITOR_INTERVAL_SECONDS=10 "$PY" -m app.main >"$TMP/server.log" 2>&1 &
  PID=$!
  trap 'kill $PID 2>/dev/null || true' EXIT
  for _ in $(seq 1 40); do curl -sf "http://127.0.0.1:$PORT/api/health" >/dev/null && break; sleep 0.25; done
  BASE_URL="http://127.0.0.1:$PORT" NODE_PATH="${NODE_PATH:-$(npm root -g)}" node scripts/ui_check.js "$TMP/shots"
  echo "스크린샷: $TMP/shots"
fi
echo "== 모든 점검 통과"
