@echo off
REM ===== Uma League one-click starter (Windows CMD) =====
REM This script creates venv, installs deps, runs migrations, loads fixtures (if db not present), then starts server.

setlocal ENABLEDELAYEDEXPANSION

REM Jump to the folder where this script is located
cd /d "%~dp0"

echo.
echo [1/6] Checking Python...
python --version || (
  echo [ERROR] Python not found in PATH. Please install Python 3.10+ and reopen this window.
  pause
  exit /b 1
)

echo.
echo [2/6] Creating virtual environment if missing...
if not exist ".venv\Scripts\python.exe" (
  python -m venv .venv || (
    echo [ERROR] Failed to create virtual environment.
    pause
    exit /b 1
  )
)

echo.
echo [3/6] Activating virtual environment...
call ".venv\Scripts\activate.bat" || (
  echo [ERROR] Failed to activate venv.
  pause
  exit /b 1
)

echo.
echo [4/6] Installing requirements...
python -m pip install --upgrade pip
pip install -r requirements.txt || (
  echo [ERROR] Pip install failed.
  pause
  exit /b 1
)

echo.
echo [5/6] Applying migrations...
python manage.py makemigrations turf
python manage.py migrate || (
  echo [ERROR] Django migrate failed.
  pause
  exit /b 1
)

echo.
if not exist "db.sqlite3" (
  echo Detected no db.sqlite3, loading demo fixtures...
  python manage.py loaddata fixtures/initial_data.json || (
    echo [WARN] Failed to load fixtures (this is optional). Continue...
  )
) else (
  echo Existing db.sqlite3 found. Skipping fixtures.
)

echo.
echo [6/6] Starting server at http://127.0.0.1:8000/
echo Press CTRL+C to stop the server.
python manage.py runserver
