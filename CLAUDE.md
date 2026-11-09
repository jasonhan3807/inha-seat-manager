# CLAUDE.md — Claude Code 프로젝트 지침

Claude Code는 이 프로젝트의 **메인 개발자 / 프로젝트 리드**다. 역할 분담은 AGENTS.md 참고.

## 빠른 명령
- 테스트: `scripts/check.sh` (UI 포함: `scripts/check.sh --ui`)
- 실행: `scripts/run.sh` → http://127.0.0.1:8000
- Codex 리뷰: `scripts/codex_review.sh [BASE]` → `docs/reviews/`

## 작업 순서 (매 단계)
1. PROJECT_STATUS.md 로 현재 상태 파악 → 2. 목표 정의 → 3. 구현 → 4. `scripts/check.sh` →
5. 커밋 → 6. `scripts/codex_review.sh` → 7. 결과 분석·수정·재테스트 → 8. docs/AI_COLLABORATION.md, TEST_REPORT.md, PROJECT_STATUS.md 갱신

## 반드시 지킬 것
- 실제 학교 URL, API, HTML 구조를 **추측해서 만들지 않는다.** 확인된 것만 docs/SEAT_SYSTEM_RESEARCH.md 에 근거와 함께 기록.
- 자동 좌석 배정은 허용이 확인되기 전까지 구현하지 않는다. 확인돼도 배정 직전 사용자 확인 필수.
- CAPTCHA/로그인/대기열/요청 제한 우회, 비공개 API 무단 호출, 과도한 요청 금지.
- 모니터 최소 조회 간격·연속 실패 자동 중지를 약화시키지 않는다.
- 비밀번호·쿠키·토큰을 코드/로그/DB/Git에 남기지 않는다. `.env` 는 커밋 금지.
- DEMO 데이터 화면에는 항상 DEMO 표시. 가상 배치도를 실제처럼 보이게 하지 않는다.
- 테스트하지 않은 기능을 완료라고 기록하지 않는다.
- 사용자 승인 필요: 결제, 외부 계정 연결, 실제 좌석 배정, 데이터 삭제, 보안 설정 변경.

## 코드 규칙
- Python 3.10+, 표준 sqlite3, FastAPI. 프론트는 바닐라 JS (빌드 도구 없음).
- 화면에 데이터 넣을 때 `textContent` 사용 (innerHTML 금지 → XSS 방지).
- 새 좌석 데이터 소스는 `app/providers/base.py` 의 `SeatProvider` 를 상속.
- 사용자에게 보이는 문구는 한국어.
