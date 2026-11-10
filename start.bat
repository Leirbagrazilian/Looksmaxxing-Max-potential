@echo off
rem One-click start for Windows: sets up on first run and opens Ascend in your browser.
rem Run "start.bat --phone" to make it reachable from your phone on the same Wi-Fi.
cd /d "%~dp0"
if not exist .venv (
  echo First run: setting up ^(takes a few minutes^)...
  py -3 -m venv .venv || python -m venv .venv
  .venv\Scripts\python -m pip install --upgrade pip >nul
  .venv\Scripts\python -m pip install -r requirements.txt
)
set HOST=127.0.0.1
if "%1"=="--phone" (
  set HOST=0.0.0.0
  echo On your phone, open http://YOUR-PC-IP:8000  ^(find the IP with: ipconfig^)
)
start "" http://127.0.0.1:8000
.venv\Scripts\python -m looksmax.web --host %HOST% --port 8000
