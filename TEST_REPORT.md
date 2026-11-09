# TEST_REPORT

_실행일: 2026-11-09 · 환경: Ubuntu 24.04, Python 3.13.18, Chromium(Playwright)_

## 요약

| 구분 | 결과 |
|---|---|
| 자동 테스트 (pytest) | **36 / 36 통과** |
| 브라우저 UI 점검 (PC 1280px, iPhone 13) | **통과** — 콘솔 오류 0, 가로 넘침 없음 |
| 실제 서버 수동 시나리오 | **통과** (아래) |
| Codex 독립 리뷰 | **미실행** — Codex 로그인 필요 |
| 실제 학교 시스템 연동 | **해당 없음** — 연동 비활성 |

## 요구 항목별 결과

| 항목 | 방법 | 결과 |
|---|---|---|
| 서버 실행 | 실제 실행 + `/api/health` | ✅ |
| 데이터베이스 연결 | health `db: true`, CRUD 테스트 | ✅ |
| 좌석 목록 표시 | API 테스트 + UI 점검(54석 표시) | ✅ |
| 좌석 상태 변경 | mock tick / set_status 테스트 | ✅ |
| 좌석 선택 | UI: 좌석 클릭 → 상세창 | ✅ |
| 희망 좌석 저장 | API CRUD, 중복 409, 최대 30개 | ✅ |
| 모니터링 시작/중지 | API + 백그라운드 실행 테스트 + UI | ✅ |
| 빈자리 감지 | 단위 테스트 + 실서버 (알림 문구 확인) | ✅ |
| 중복 알림 방지 | 계속 빈자리 / 쿨다운 / 쿨다운 후 재알림 테스트 | ✅ |
| 오류·연결 끊김 처리 | 실패 주입 → 백오프 5→10→20→40초, 5회 후 자동 중지 + 시스템 알림 (실서버) | ✅ |
| 공식 연동 비활성 시 | official 모드: 화면 정상, 조회 503, 배정 403, 모니터 즉시 중지 | ✅ |
| 모바일 레이아웃 | iPhone 13 에뮬레이션, 좌석 배치도 넘침 검사 | ✅ |
| 보안·설정 검증 | 교차 출처 POST 403, 폼 본문 거부, 보안 헤더, 간격 최소값 강제 | ✅ |
| 배정 확인 절차 | confirm 없으면 400, 빈자리 아니면 409, 이력에 [DEMO] | ✅ |

## 실서버 시나리오 기록
1. 희망 좌석(DEMO 열람실 A 1번) 사용 중 → 모니터링 시작 → 빈자리로 변경 → 약 5초 안에 알림 생성
   ```
   [DEMO] 빈자리 감지: DEMO 열람실 A 1번
   감지 시각: 2026-11-09 12:01:09
   현재 상태: 빈자리
   배정은 공식 페이지에서 직접 진행하세요: https://lib.inha.ac.kr
   ```
2. 조회 실패 20회 주입 → 실패 5회째 `running: false`, "조회가 5회 연속 실패하여 모니터링을 자동 중지했습니다." 시스템 알림

## UI 점검 중 발견·수정한 문제
- 알림 배지가 0일 때도 표시됨 → 수정 후 재확인
- 모바일 좌석 배치도 오른쪽 잘림 → 수정, 점검 항목(`seatMapFits`) 추가

## 테스트하지 않은 것
- 실제 학교 시스템 (연동 없음)
- Windows/macOS 실제 실행 (`run.bat`, `run.sh` 는 Linux 클라우드 환경에서만 확인: run.sh 미실행, 동일 명령은 수동 확인)
- 실제 휴대폰 기기, 브라우저 알림 팝업 (헤드리스 브라우저에서는 권한 팝업 확인 불가)

## 재현 방법
```bash
scripts/check.sh --ui
```

## 테스트 목록
- `tests/test_api.py::test_index_page_has_demo`
- `tests/test_api.py::test_static_files`
- `tests/test_api.py::test_health_and_system`
- `tests/test_api.py::test_rooms_and_seats`
- `tests/test_api.py::test_watch_crud`
- `tests/test_api.py::test_watch_limit`
- `tests/test_api.py::test_monitor_requires_watch`
- `tests/test_api.py::test_monitor_flow_and_notifications`
- `tests/test_api.py::test_monitor_start_stop_background`
- `tests/test_api.py::test_interval_api`
- `tests/test_api.py::test_assign_requires_confirm`
- `tests/test_api.py::test_demo_fail_shows_error`
- `tests/test_api.py::test_cross_origin_post_blocked`
- `tests/test_api.py::test_non_json_body_rejected`
- `tests/test_monitor.py::test_no_watches_no_query`
- `tests/test_monitor.py::test_detects_available_and_message`
- `tests/test_monitor.py::test_no_duplicate_while_still_available`
- `tests/test_monitor.py::test_cooldown_blocks_flapping`
- `tests/test_monitor.py::test_renotify_after_cooldown`
- `tests/test_monitor.py::test_multiple_seats_one_query_per_room`
- `tests/test_monitor.py::test_failures_backoff_and_autostop`
- `tests/test_monitor.py::test_failure_counter_resets_on_success`
- `tests/test_monitor.py::test_backoff_capped`
- `tests/test_monitor.py::test_interval_clamped`
- `tests/test_monitor.py::test_interval_persisted`
- `tests/test_monitor.py::test_official_provider_stops_immediately`
- `tests/test_monitor.py::test_start_stop_persist_flag`
- `tests/test_official_mode.py::test_official_mode_degrades_gracefully`
- `tests/test_providers.py::test_mock_rooms_are_demo`
- `tests/test_providers.py::test_mock_seed_is_reproducible`
- `tests/test_providers.py::test_mock_tick_changes_some_seats`
- `tests/test_providers.py::test_mock_fail_next`
- `tests/test_providers.py::test_mock_unknown_room`
- `tests/test_providers.py::test_mock_assign_only_available`
- `tests/test_providers.py::test_official_provider_is_disabled`
- `tests/test_providers.py::test_create_provider`
