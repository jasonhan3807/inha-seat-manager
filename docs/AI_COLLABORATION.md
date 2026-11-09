# AI 협업 기록 (Claude Code ↔ Codex CLI)

## 협업 구조

| 역할 | 담당 | 권한 |
|---|---|---|
| Claude Code | 메인 개발자 / 프로젝트 리드: 설계, 구현, 테스트, 통합, 문서 | 작업 브랜치에 커밋 |
| Codex CLI | 독립 리뷰어: 버그, 보안, 요구사항 누락, 테스트 누락 검토 | **읽기 전용** (코드 수정 불가) |

## 실행 방식

```
Claude 구현 → scripts/check.sh (테스트) → 커밋
  → scripts/codex_review.sh [BASE]   # Codex 읽기 전용 리뷰
  → docs/reviews/codex-review-*.md   # 결과 저장
  → Claude가 결과 분석 → 수정 → 재테스트 → 커밋 → (필요시 재리뷰)
  → 이 문서에 기록
```

`scripts/codex_review.sh` 의 안전 장치:
- Codex를 `--sandbox read-only` 로 실행 → 파일을 바꿀 수 없음
- 커밋된 내용만 담은 **임시 git worktree** 에서 실행 → `.env` 같은 Git 밖 파일은 Codex에 보이지 않음
- ChatGPT 계정 로그인일 때만 실행. API 키 로그인(사용량 과금 가능)이면 중단 (`ALLOW_API_BILLING=1` 로만 허용)
- 로그인 안 되어 있으면 중단하고 안내만 출력

MCP는 쓰지 않는다. 에이전트 간 호출은 위 스크립트로 직접 처리한다.

## Codex 실행 환경 확인 (2026-11-09)

| 항목 | 결과 |
|---|---|
| 설치 여부 | 처음엔 없음 → `npm install -g @openai/codex` 로 설치 (클라우드 세션 안) |
| 버전 | codex-cli 0.167.0 |
| 로그인 상태 | **Not logged in** |
| 인증 방식 | 없음. 공식 방식: `codex login` (ChatGPT 계정) 또는 `--device-auth`, 또는 API 키 |
| 과금 | ChatGPT 구독으로 사용 가능한지는 사용자 계정 플랜에 따라 다르므로 확인 필요. API 키 방식은 사용량 과금 |

→ 사용자 인증이 필요해 Codex 리뷰는 **아직 실행하지 못함**.

---

## 협업 작업 #1 — P0~P2 프로젝트 기반 + DEMO MVP

- **작업 목표**: 프로젝트 구조, 모의 데이터 기반 좌석 확인·희망 좌석·모니터링·알림 MVP
- **Claude 구현 내용**: FastAPI 앱, SQLite 저장소, Mock/Official 데이터 제공자, 모니터(중복 알림 방지·백오프·자동 중지), 반응형 대시보드, 테스트 36개, UI 자동 점검 스크립트, Codex 리뷰 스크립트
- **Codex 검토 결과**: **미실행** — Codex CLI 로그인 안 됨 (사용자 인증 필요)
- **심각도별 발견 사항**: 없음 (리뷰 미실행)
- **Claude 자체 점검에서 찾아 고친 문제**:
  - [HIGH] `/api/monitor/start` 가 동기 함수라 스레드에서 실행되어 백그라운드 모니터링이 실제로 시작되지 않음 → async 엔드포인트로 수정, 회귀 테스트 추가
  - [MEDIUM] 알림 개수 배지가 0일 때도 보임 (CSS가 `hidden` 속성을 덮어씀) → 수정
  - [MEDIUM] 모바일에서 좌석 배치도 오른쪽이 잘림 → 좁은 화면용 좌석 크기 적용, UI 점검에 넘침 검사 추가
- **테스트 결과**: pytest 36/36 통과, PC·모바일 UI 점검 통과 (TEST_REPORT.md)
- **최종 상태**: Codex 리뷰 대기. 사용자가 `codex login` 후 `scripts/codex_review.sh` 실행 필요
