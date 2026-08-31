@echo off
rem 스케줄러용 러너 — 로그를 logs\refresh_YYYY-MM-DD.log 에 남김
cd /d "%~dp0.."
if not exist logs mkdir logs
for /f %%d in ('powershell -NoProfile -Command "(Get-Date).ToString(\"yyyy-MM-dd\")"') do set TODAY=%%d
python scripts\refresh_all.py >> "logs\refresh_%TODAY%.log" 2>&1
