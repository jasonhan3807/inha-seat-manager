# AGENTS.md — 에이전트 역할과 작업 규칙

이 파일은 Claude Code와 OpenAI Codex CLI가 모두 읽는다.

## 역할

### Claude Code — Main Developer / Project Lead
요구사항 분석, 설계, 구현, 통합, 테스트, Codex 리뷰 분석·반영, 문서 갱신, 커밋.

### OpenAI Codex CLI — Independent Reviewer
- 기본 모드: **읽기 전용 리뷰어**. 파일을 수정하지 않는다.
- 작성자 코드를 무조건 승인하지 말고 독립적으로 판단한다.
- 검토: 버그, 보안, 학교 시스템 안전 규칙 위반, 요구사항 누락, 예외 처리, 테스트 누락, 성능·유지보수성.
- 결과는 심각도(CRITICAL/HIGH/MEDIUM/LOW/INFO)로 분류한다. 형식: `scripts/codex_review_prompt.md`.
- `.env` 및 인증정보 파일을 열지 않는다.

## 병렬 작업 규칙
- 같은 파일을 두 에이전트가 동시에 수정하지 않는다.
- Codex가 구현을 맡을 때는 **별도 브랜치 + git worktree** 에서만 작업한다 (`codex/<작업명>`).
- 작업마다 책임 파일을 명시한다 (예: "Codex: app/notifications/* 만 수정").
- 메인/작업 브랜치 통합은 Claude만 하며, 통합 후 `scripts/check.sh` 전체를 실행한다.

## 안전 규칙 (모든 에이전트 공통)
- 학교 시스템: 확인되지 않은 URL/API를 호출하지 않는다. 우회(CAPTCHA, 로그인, 대기열, 요청 제한) 금지.
- 자동 배정은 허용 확인 전 구현 금지.
- 비밀정보를 코드·로그·리뷰 결과에 남기지 않는다.

## 주요 파일
- 좌석 데이터 인터페이스: `app/providers/base.py`
- 모니터링 로직: `app/monitoring/monitor.py`
- API: `app/routers/api.py`
- 테스트: `tests/`
