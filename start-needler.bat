@echo off
rem Start Needler on Windows: creates its Python environment on first run.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Setting up Needler for the first time...
  python -m venv .venv || goto :error
  ".venv\Scripts\python.exe" -m pip install --upgrade pip || goto :error
  ".venv\Scripts\python.exe" -m pip install -e . || goto :error
)
set PYTHONPATH=src
start "" http://127.0.0.1:5050
".venv\Scripts\python.exe" -X utf8 -m embroiderly.web
goto :eof
:error
echo Setup failed. Install Python 3.11 or newer from https://www.python.org and try again.
pause
