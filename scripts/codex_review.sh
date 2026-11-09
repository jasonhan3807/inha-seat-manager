#!/usr/bin/env bash
# Codex CLI 독립 코드 리뷰 실행 스크립트
#
# 사용법:  scripts/codex_review.sh [BASE]
#   BASE: 비교 기준 커밋/브랜치 (기본값: HEAD~1, 첫 커밋이면 전체)
#
# 안전 장치
# - Codex는 읽기 전용(read-only)으로 실행한다. 코드를 직접 바꾸지 않는다.
# - 커밋된 내용만 담은 임시 git worktree에서 실행하므로 .env 등 Git에 없는 파일은 Codex에 보이지 않는다.
# - ChatGPT 계정 로그인 상태에서만 실행한다. API 키 로그인(사용량 과금 가능)은 ALLOW_API_BILLING=1 일 때만 허용.
# - 결과는 docs/reviews/ 에 저장한다.
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

if ! command -v codex >/dev/null 2>&1; then
  echo "[중단] Codex CLI가 설치되어 있지 않습니다. 설치: npm install -g @openai/codex" >&2
  exit 10
fi

STATUS="$(codex login status 2>&1 || true)"
if echo "$STATUS" | grep -qi "not logged in"; then
  echo "[중단] Codex CLI에 로그인되어 있지 않습니다. 터미널에서 'codex login' 을 실행해 ChatGPT 계정으로 로그인하세요." >&2
  exit 11
fi
if echo "$STATUS" | grep -qi "api key" && [ "${ALLOW_API_BILLING:-0}" != "1" ]; then
  echo "[중단] Codex가 API 키로 로그인되어 있어 사용량 요금이 발생할 수 있습니다." >&2
  echo "       ChatGPT 계정으로 다시 로그인하거나, 비용에 동의한다면 ALLOW_API_BILLING=1 로 실행하세요." >&2
  exit 12
fi

EMPTY_TREE="$(git hash-object -t tree /dev/null)"
BASE="${1:-}"
if [ -z "$BASE" ]; then
  if git rev-parse -q --verify HEAD~1 >/dev/null; then BASE="HEAD~1"; else BASE="$EMPTY_TREE"; fi
fi

TS="$(date +%Y%m%d-%H%M%S)"
OUT_DIR="$ROOT/docs/reviews"
OUT="$OUT_DIR/codex-review-$TS.md"
WT="$(mktemp -d)/review-wt"
mkdir -p "$OUT_DIR"

cleanup() { git worktree remove --force "$WT" >/dev/null 2>&1 || true; }
trap cleanup EXIT
git worktree add --detach "$WT" HEAD >/dev/null

PROMPT="$(cat "$ROOT/scripts/codex_review_prompt.md")"
echo "[실행] Codex 리뷰: $BASE..HEAD  (읽기 전용, worktree: $WT)"

{
  echo "# 변경 파일"
  git diff --stat "$BASE" HEAD
  echo
  echo "# Diff"
  git diff "$BASE" HEAD
} | codex exec \
    --cd "$WT" \
    --sandbox read-only \
    --ephemeral \
    --output-last-message "$OUT" \
    "$PROMPT"

{
  echo
  echo "---"
  echo "_리뷰 범위: \`$BASE..$(git rev-parse --short HEAD)\` · 생성: $TS · Codex $(codex --version 2>/dev/null)_"
} >> "$OUT"

echo "[완료] 결과: $OUT"
