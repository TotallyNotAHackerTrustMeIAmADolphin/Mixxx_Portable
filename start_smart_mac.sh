#!/bin/bash

# Get the folder where THIS script is located
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DATA_DIR="$DIR/Mixxx_Data"
SCRIPT_DIR="$DIR/Scripts"
MIXXX_EXE="/Applications/Mixxx.app/Contents/MacOS/mixxx"

clear
echo "=========================================="
echo "    MIXXX SMART LAUNCHER (macOS)         "
echo "=========================================="

# 1. Check for Python 3
# macOS usually prompts to install Command Line Tools if python3 is missing
if ! command -v python3 &> /dev/null; then
    echo "❌ ERROR: Python 3 is not installed."
    echo "Please download Python from https://www.python.org/downloads/macos/"
    echo "or install Apple Command Line Tools."
    read -p "Press Enter to exit..."
    exit 1
fi

# 2. Check for Mixxx in the Applications folder
if [ ! -f "$MIXXX_EXE" ]; then
    echo "❌ ERROR: Mixxx not found at $MIXXX_EXE"
    echo "Please ensure Mixxx is installed in your Applications folder."
    echo "Download: https://mixxx.org/download/"
    read -p "Press Enter to exit..."
    exit 1
fi

# 3. Run Path Fixer (LOAD mode)
# This will also trigger the "Already Running" check within Python
python3 "$SCRIPT_DIR/mixxx_path_fixer.py" "$DATA_DIR" "mac" "load"

# Check if Python script exited successfully (e.g., didn't hit 'Already Running' block)
if [ $? -eq 0 ]; then
    echo "🚀 Launching Mixxx..."
    echo "NOTE: If tracks don't load, grant Mixxx 'Removable Volumes' access"
    echo "in System Settings > Privacy & Security > Files and Folders."
    
    # 4. Launch Mixxx with the portable settings path
    "$MIXXX_EXE" --settingsPath "$DATA_DIR"
    
    # 5. Run Path Fixer (SAVE mode)
    echo "------------------------------------------"
    echo "Mixxx closed. Saving machine settings..."
    python3 "$SCRIPT_DIR/mixxx_path_fixer.py" "$DATA_DIR" "mac" "save"
    echo "Done. Safe to eject drive."
else
    # If python exited with error (like already running), stay open for a second
    sleep 2
fi