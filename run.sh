#!/usr/bin/env bash
# ==============================================================================
# Beat Strobe - Audio Color Strober (macOS / Linux Launcher)
# ==============================================================================

set -e

# Change to script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "⚡ Starting Beat Strobe..."

# Locate suitable Python binary
PYTHON_BIN=""

if [[ -f "$SCRIPT_DIR/.venv/bin/python" ]]; then
    PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
elif [[ -f "$SCRIPT_DIR/venv/bin/python" ]]; then
    PYTHON_BIN="$SCRIPT_DIR/venv/bin/python"
elif command -v python3 &>/dev/null; then
    PYTHON_BIN="python3"
elif command -v python &>/dev/null; then
    PYTHON_BIN="python"
else
    echo "❌ Error: Python 3 was not found on your system."
    echo "Please install Python 3 (e.g. brew install python) and try again."
    exit 1
fi

# Verify dependencies
if ! "$PYTHON_BIN" -c "import pygame, numpy, soundcard" 2>/dev/null; then
    echo "📦 Required packages (pygame, numpy, soundcard) not found in $PYTHON_BIN."
    
    # If not using a venv, offer/auto-create a local virtualenv
    if [[ "$PYTHON_BIN" != *".venv"* && "$PYTHON_BIN" != *"venv"* ]]; then
        echo "⚙️ Setting up virtual environment at .venv..."
        "$PYTHON_BIN" -m venv "$SCRIPT_DIR/.venv"
        PYTHON_BIN="$SCRIPT_DIR/.venv/bin/python"
    fi

    echo "📥 Installing dependencies from requirements.txt..."
    "$PYTHON_BIN" -m pip install -r "$SCRIPT_DIR/requirements.txt"
fi

# Launch application
echo "🚀 Launching Beat Strobe..."
exec "$PYTHON_BIN" "$SCRIPT_DIR/main.py" "$@"
