@echo off
rem Scheduler runner - writes daily log to logs\refresh_YYYY-MM-DD.log
cd /d "%~dp0.."
if not exist logs mkdir logs
for /f %%d in ('powershell -NoProfile -Command "(Get-Date).ToString(\"yyyy-MM-dd\")"') do set TODAY=%%d
python scripts\refresh_all.py >> "logs\refresh_%TODAY%.log" 2>&1
