#!/bin/bash
# Get the folder where THIS script is
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
DATA_DIR="$DIR/Mixxx_Data"
SCRIPT_DIR="$DIR/Scripts"
MIXXX_EXE="/Applications/Mixxx.app/Contents/MacOS/mixxx"

echo "[macOS MODE] Preparing portable environment..."

# 1. Prepare Environment (LOAD mode)
# Mac uses the 'linux' pathing logic (forward slashes)
python3 "$SCRIPT_DIR/mixxx_path_fixer.py" "$DATA_DIR" "mac" "load"

# 2. Launch Mixxx
if [ ! -f "$MIXXX_EXE" ]; then
    echo "Error: Mixxx not found at $MIXXX_EXE"
    echo "Please ensure Mixxx is installed in your Applications folder."
    read -p "Press enter to exit..."
    exit 1
fi

"$MIXXX_EXE" --settingsPath "$DATA_DIR"

# 3. Post-Flight (SAVE mode)
echo "Mixxx closed. Saving machine-specific hardware settings..."
python3 "$SCRIPT_DIR/mixxx_path_fixer.py" "$DATA_DIR" "mac" "save"