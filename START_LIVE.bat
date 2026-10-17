@echo off
title Asset Intelligence Copilot - live supervisor
cd /d "%~dp0"
echo.
echo   Starting the copilot and keeping it live.
echo   Leave this window open. The public link is printed here and
echo   saved to .live_url when the tunnel is up.
echo.
python scripts\keep_live.py
pause
