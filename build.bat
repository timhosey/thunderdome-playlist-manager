@echo off
REM Build a double-click .exe for Windows.
REM Run this ON Windows - PyInstaller does not cross-compile.
cd /d "%~dp0"

if not exist .venv (
    python -m venv .venv
)
call .venv\Scripts\activate.bat

pip install -q -r requirements.txt
pip install -q pyinstaller

pyinstaller --noconfirm thunderdome.spec

echo.
echo Build complete: dist\ThunderdomePlaylistManager.exe
