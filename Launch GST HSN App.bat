@echo off
setlocal

cd /d "%~dp0"
python -m gst_hsn_tool

if errorlevel 1 (
  echo.
  echo Failed to start app. Ensure Python and dependencies are installed.
  pause
)
