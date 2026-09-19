@echo off
REM ==
REM weekly_check.bat
REM Runs check_stock.py from wherever this file actually lives, so it
REM works no matter what folder Windows Task Scheduler starts it from.
REM See README.md for the one-time command that schedules this weekly.
REM ==
cd /d "%~dp0"
python check_stock.py >> weekly_check.log 2>&1
