@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Python environment not found. Create .venv and install dependencies.
  pause
  exit /b 1
)
if not exist "webapp\frontend\dist\index.html" (
  echo Build the interface first: cd webapp\frontend ^&^& npm ci ^&^& npm run build
  pause
  exit /b 1
)
".venv\Scripts\python.exe" -B -m webapp %*
if errorlevel 1 pause
