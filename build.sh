#!/usr/bin/env bash
# Build a double-click executable for the current platform (Linux/macOS).
# Run this ON the target OS - PyInstaller does not cross-compile.
set -e
cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi
source .venv/bin/activate

pip install -q -r requirements.txt
pip install -q pyinstaller

pyinstaller --noconfirm thunderdome.spec

echo
echo "Build complete: dist/ThunderdomePlaylistManager"
