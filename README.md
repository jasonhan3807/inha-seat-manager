# INHA SEAT MANAGER

인하대학교 정석학술정보관 일반열람실 **빈자리 모니터링 · 알림** 개인용 프로그램입니다.

> ⚠️ **현재는 DEMO(모의 데이터) 모드입니다.** 화면의 열람실·좌석 배치·상태는 가상 데이터이며 실제 학교 구조가 아닙니다.
> 학교 시스템의 공식 연동 방법이 확인되지 않아 실제 데이터 연동과 자동 배정은 하지 않습니다. ([조사 결과](docs/SEAT_SYSTEM_RESEARCH.md))
> 이 프로그램은 학교 공식 서비스가 아닙니다.

## 주요 기능

- 열람실 선택, 좌석 배치도 (빈자리 ○ / 사용 중 ● / 자리비움 ◐ / 사용 불가 ✕ — 색 + 아이콘 + 글자로 구분)
- 좌석 상세 보기, 희망 좌석 등록/삭제 (최대 30개)
- 희망 좌석 빈자리 모니터링: 시작/중지, 조회 간격 설정(최소 10초), 지금 확인
- 빈자리 알림: 대시보드 알림 + 브라우저 알림 + 소리 (중복 알림 방지, 같은 좌석 5분 쿨다운)
- 조회 실패 시 간격 자동 증가, 5회 연속 실패 시 자동 중지 + 알림
- 조회·모니터링·배정 이력, 시스템 상태 화면
- 공식 정석학술정보관 페이지 바로가기 (실제 배정은 사용자가 직접)
- PC / 모바일 반응형, 다크 모드

## 설치 및 실행

필요한 것: **Python 3.10 이상**, Git

### Windows

명령 프롬프트(cmd) 또는 PowerShell에서:

```bat
git clone https://github.com/jasonhan3807/inha-seat-manager.git
cd inha-seat-manager
scripts\run.bat
```

### macOS / Linux

터미널에서:

```bash
git clone https://github.com/jasonhan3807/inha-seat-manager.git
cd inha-seat-manager
scripts/run.sh
```

처음 실행하면 가상환경(`.venv`, 이 프로젝트 전용 파이썬 라이브러리 폴더)을 만들고 필요한 라이브러리를 설치합니다.
그다음 브라우저에서 **http://127.0.0.1:8000** 을 엽니다. 종료는 터미널에서 `Ctrl+C`.

### 휴대폰에서 보기 (선택)

기본 설정은 보안을 위해 **이 PC에서만** 접속됩니다. 같은 와이파이의 휴대폰에서 보려면 `.env` 에서 `HOST=0.0.0.0` 으로 바꾸고,
휴대폰 브라우저에서 `http://<PC의 IP 주소>:8000` 을 엽니다. (공용 와이파이에서는 권장하지 않습니다 — [SECURITY.md](SECURITY.md))

## 사용 방법

1. **좌석 배치도** 탭에서 열람실을 고르고 원하는 좌석을 누릅니다 → **희망 좌석에 추가**
2. **대시보드**에서 **▶ 시작**을 누르면 모니터링이 시작됩니다.
3. **설정·상태** 탭에서 **브라우저 알림 허용하기**를 누르면 다른 창을 보고 있어도 알림이 옵니다.
4. 빈자리 알림이 오면 **공식 정석학술정보관 페이지**에서 직접 배정하세요.

## 설정 (`.env`)

`.env.example` 을 `.env` 로 복사해 수정합니다. (실행 스크립트가 자동으로 복사합니다)

| 항목 | 기본값 | 설명 |
|---|---|---|
| `SEAT_PROVIDER` | `mock` | `mock`=DEMO 데이터, `official`=공식 연동(현재 비활성) |
| `MONITOR_INTERVAL_SECONDS` | `30` | 조회 간격(초) |
| `MONITOR_MIN_INTERVAL_SECONDS` | `10` | 최소 조회 간격 |
| `MONITOR_MAX_FAILURES` | `5` | 연속 실패 시 자동 중지 횟수 |
| `NOTIFY_COOLDOWN_SECONDS` | `300` | 같은 좌석 재알림 간격 |
| `OFFICIAL_SEAT_URL` | `https://lib.inha.ac.kr` | 공식 페이지 주소 |

## 개발자용

```bash
scripts/check.sh          # 테스트 실행
scripts/check.sh --ui     # 테스트 + 브라우저(PC/모바일) UI 점검 (Node + Playwright 필요)
scripts/codex_review.sh   # Codex CLI 독립 코드 리뷰 (codex login 필요)
```

구조

```
app/
  main.py            앱 생성, 보안 미들웨어
  config.py          .env 설정
  database/db.py     SQLite (희망 좌석, 알림, 이력, 설정)
  providers/         좌석 데이터: mock.py(DEMO), official.py(비활성)
  monitoring/        빈자리 모니터링 (중복 방지, 백오프, 자동 중지)
  notifications/     알림 문구
  routers/           api.py(JSON API), pages.py(화면)
  templates/, static/ 화면 (HTML/CSS/JS, 외부 라이브러리 없음)
tests/               pytest
scripts/             실행/점검/리뷰 스크립트
docs/                조사·협업 기록
```

API 문서: 실행 후 http://127.0.0.1:8000/api/docs

## 문서

[PROJECT_STATUS.md](PROJECT_STATUS.md) · [ROADMAP.md](ROADMAP.md) · [TEST_REPORT.md](TEST_REPORT.md) · [SECURITY.md](SECURITY.md) ·
[좌석 시스템 조사](docs/SEAT_SYSTEM_RESEARCH.md) · [AI 협업](docs/AI_COLLABORATION.md) · [AGENTS.md](AGENTS.md) · [CLAUDE.md](CLAUDE.md)
