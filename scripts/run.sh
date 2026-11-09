#!/usr/bin/env bash
# 프로그램 실행 (macOS / Linux). 처음이면 가상환경을 만들고 라이브러리를 설치한다.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi
[ -f .env ] || cp .env.example .env
echo "브라우저에서 http://127.0.0.1:8000 을 여세요. (종료: Ctrl+C)"
exec .venv/bin/python -m app.main
