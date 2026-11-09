@echo off
REM 프로그램 실행 (Windows). 처음이면 가상환경을 만들고 라이브러리를 설치한다.
cd /d "%~dp0\.."
if not exist .venv (
  python -m venv .venv
  .venv\Scripts\pip install -r requirements.txt
)
if not exist .env copy .env.example .env
echo 브라우저에서 http://127.0.0.1:8000 을 여세요. (종료: Ctrl+C)
.venv\Scripts\python -m app.main
